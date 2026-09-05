from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from urllib.parse import urlsplit

import pyotp
import pytest
from sqlalchemy import select

from cofrap.domain.models import six_months_after
from cofrap.infrastructure.database import UserRow

pytestmark = pytest.mark.integration


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def register(client, username="alice"):
    response = client.post("/api/users", json={"username": username})
    assert response.status_code == 201, response.text
    return response.json()


def redeem(client, registration):
    token = urlsplit(registration["delivery_url"]).fragment
    response = client.post("/api/password-deliveries/redeem", json={"token": token})
    assert response.status_code == 200, response.text
    return response.json()["password"]


def activate(client, clock, username="alice"):
    registration = register(client, username)
    password = redeem(client, registration)
    headers = bearer(registration["enrollment_token"])
    setup = client.post("/api/enrollment/totp", headers=headers)
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    result = client.post(
        "/api/enrollment/confirm",
        headers=headers,
        json={"code": pyotp.TOTP(secret).at(clock())},
    )
    assert result.status_code == 200, result.text
    assert result.json()["mfa_confirmed"]
    clock.advance()
    return password, secret


def login(client, clock, password, secret):
    return client.post(
        "/api/auth/login",
        json={
            "username": "alice",
            "password": password,
            "code": pyotp.TOTP(secret).at(clock()),
        },
    )


def test_complete_enrollment_login_logout(client, clock, database):
    password, secret = activate(client, clock)
    response = login(client, clock, password, secret)
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "authenticated"
    headers = bearer(result["token"])
    me = client.get("/api/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == "alice"
    assert password not in me.text and secret not in me.text
    with database() as session:
        user = session.scalar(select(UserRow))
        assert user.password_hash.startswith("$argon2id$")
        assert secret not in user.totp_ciphertext
        assert user.delivery_ciphertext is None and user.delivery_digest is None
        assert user.enrollment_digest is None
        assert user.session_digest != result["token"]
    assert login(client, clock, password, secret).status_code == 401
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/me", headers=headers).status_code == 401


def test_password_delivery_is_atomic_even_with_concurrent_requests(client):
    registration = register(client)
    token = urlsplit(registration["delivery_url"]).fragment
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(
            executor.map(
                lambda _: client.post("/api/password-deliveries/redeem", json={"token": token}),
                range(2),
            )
        )
    assert sorted(response.status_code for response in responses) == [200, 401]


def test_totp_cannot_be_generated_before_password_delivery(client):
    registration = register(client)
    headers = bearer(registration["enrollment_token"])
    assert client.post("/api/enrollment/totp", headers=headers).status_code == 409


def test_inactive_account_cannot_login_and_setup_is_idempotent(client, clock):
    registration = register(client)
    password = redeem(client, registration)
    headers = bearer(registration["enrollment_token"])
    first = client.post("/api/enrollment/totp", headers=headers).json()
    second = client.post("/api/enrollment/totp", headers=headers).json()
    assert first["secret"] == second["secret"]
    assert login(client, clock, password, first["secret"]).status_code == 401


def test_expiry_requires_old_factors_then_rotates_both_credentials(client, clock, database):
    password, secret = activate(client, clock)
    with database() as session:
        generated = session.scalar(select(UserRow)).generated_at
    clock.now = six_months_after(generated)
    assert login(client, clock, "wrong", secret).status_code == 401
    response = login(client, clock, password, secret)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "renewal_required"
    assert client.get("/api/me", headers=bearer(result["token"])).status_code == 401
    with database() as session:
        assert session.scalar(select(UserRow)).expired
    headers = bearer(result["token"])
    renewal = client.post("/api/credentials/renew", headers=headers)
    assert renewal.status_code == 200, renewal.text
    assert client.post("/api/credentials/renew", headers=headers).status_code == 401
    renewed = renewal.json()
    new_password = redeem(client, renewed)
    assert new_password != password
    headers = bearer(renewed["enrollment_token"])
    new_secret = client.post("/api/enrollment/totp", headers=headers).json()["secret"]
    assert new_secret != secret
    assert (
        client.post(
            "/api/enrollment/confirm",
            headers=headers,
            json={
                "code": pyotp.TOTP(new_secret).at(clock()),
            },
        ).status_code
        == 200
    )
    clock.advance()
    assert login(client, clock, password, secret).status_code == 401
    assert login(client, clock, new_password, new_secret).json()["status"] == "authenticated"
    with database() as session:
        assert not session.scalar(select(UserRow)).expired


def test_just_before_expiry_still_authenticates(client, clock, database):
    password, secret = activate(client, clock)
    with database() as session:
        generated = session.scalar(select(UserRow)).generated_at
    clock.now = six_months_after(generated) - timedelta(seconds=1)
    result = login(client, clock, password, secret).json()
    assert result["status"] == "authenticated"
    clock.advance(1)
    assert client.get("/api/me", headers=bearer(result["token"])).status_code == 401


def test_expired_delivery_and_enrollment_are_rejected(client, clock):
    registration = register(client)
    clock.advance(15 * 60)
    token = urlsplit(registration["delivery_url"]).fragment
    assert client.post("/api/password-deliveries/redeem", json={"token": token}).status_code == 401
    assert (
        client.post(
            "/api/enrollment/totp", headers=bearer(registration["enrollment_token"])
        ).status_code
        == 401
    )


def test_duplicate_username_is_normalized_and_safe_under_concurrency(client):
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda name: client.post("/api/users", json={"username": name}),
                ["Alice", " alice "],
            )
        )
    assert sorted(result.status_code for result in results) == [201, 409]


def test_validation_does_not_echo_secrets(client):
    response = client.post(
        "/api/auth/login",
        json={
            "username": "<script>",
            "password": "PRIVATE_PASSWORD",
            "code": "PRIVATE_TOTP",
        },
    )
    assert response.status_code == 422
    assert "PRIVATE" not in response.text
    assert (
        client.post("/api/users", json={"username": "alice", "expired": False}).status_code == 422
    )


def test_capability_scopes_are_not_interchangeable(client):
    registration = register(client)
    headers = bearer(registration["enrollment_token"])
    assert client.get("/api/me", headers=headers).status_code == 401
    assert client.post("/api/credentials/renew", headers=headers).status_code == 401
    assert client.get("/api/me").status_code == 401


def test_health_checks(client):
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").json()["database"] == "postgresql"


def test_concurrent_login_cannot_reuse_one_totp_code(client, clock):
    password, secret = activate(client, clock)
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: login(client, clock, password, secret), range(2)))
    assert sorted(response.status_code for response in responses) == [200, 401]


def test_expired_renewal_authorization_is_rejected(client, clock):
    password, secret = activate(client, clock)
    clock.advance(200 * 24 * 3600)
    result = login(client, clock, password, secret).json()
    assert result["status"] == "renewal_required"
    clock.advance(5 * 60)
    assert client.post("/api/credentials/renew", headers=bearer(result["token"])).status_code == 401


def test_new_session_revokes_previous_one_and_expires(client, clock):
    password, secret = activate(client, clock)
    first = login(client, clock, password, secret).json()["token"]
    clock.advance()
    second = login(client, clock, password, secret).json()["token"]
    assert client.get("/api/me", headers=bearer(first)).status_code == 401
    assert client.get("/api/me", headers=bearer(second)).status_code == 200
    clock.advance(30 * 60)
    assert client.get("/api/me", headers=bearer(second)).status_code == 401


def test_incorrect_totp_does_not_activate_account(client, clock, database):
    registration = register(client)
    redeem(client, registration)
    headers = bearer(registration["enrollment_token"])
    secret = client.post("/api/enrollment/totp", headers=headers).json()["secret"]
    valid_codes = {
        pyotp.TOTP(secret).at(clock() + timedelta(seconds=offset)) for offset in (-30, 0, 30)
    }
    bad_code = next(f"{number:06d}" for number in range(10) if f"{number:06d}" not in valid_codes)
    response = client.post("/api/enrollment/confirm", headers=headers, json={"code": bad_code})
    assert response.status_code == 401
    with database() as session:
        user = session.scalar(select(UserRow))
        assert not user.mfa_confirmed and user.generated_at is None
