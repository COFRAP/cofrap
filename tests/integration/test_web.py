import re
from urllib.parse import urlsplit

import pyotp
import pytest
from test_identity import activate, bearer, register

pytestmark = pytest.mark.integration


def csrf(client):
    client.get("/")
    return {"X-CSRF-Token": client.cookies.get("cofrap_csrf"), "Origin": "http://testserver"}


def test_html_registration_delivery_totp_and_login(client, clock):
    headers = csrf(client)
    response = client.post("/web/register", data={"username": "marie"}, headers=headers)
    assert response.status_code == 200, response.text
    assert "Un accès rien qu’à vous" in response.text
    assert "data:image/png;base64," in response.text
    token = client.cookies.get("cofrap_delivery")
    enrollment_cookie = next(c for c in client.cookies.jar if c.name == "cofrap_enrollment")
    assert enrollment_cookie.has_nonstandard_attr("HttpOnly")
    assert client.get("/enrollment").status_code == 200
    delivery = client.post("/web/delivery", data={"token": token}, headers=headers)
    assert delivery.status_code == 200, delivery.text
    password = re.search(r'id="generated-password"[^>]*value="([^"]+)"', delivery.text)[1]
    from html import unescape

    password = unescape(password)
    assert len(password) == 24
    assert "Une dernière protection" in client.get("/enrollment").text
    setup = client.post("/web/enrollment/totp", headers=headers)
    assert setup.status_code == 200, setup.text
    secret = re.search(r'id="totp-secret"[^>]*value="([^"]+)"', setup.text)[1]
    confirmation = client.post(
        "/web/enrollment/confirm",
        data={
            "code": pyotp.TOTP(secret).at(clock()),
        },
        headers=headers,
    )
    assert confirmation.status_code == 200, confirmation.text
    assert "Vous êtes prêt" in confirmation.text
    assert not client.cookies.get("cofrap_enrollment")
    clock.advance()
    login = client.post(
        "/web/login",
        data={
            "username": "marie",
            "password": password,
            "code": pyotp.TOTP(secret).at(clock()),
        },
        headers=headers,
    )
    assert login.status_code == 200, login.text
    assert "Bienvenue, marie" in login.text
    assert client.get("/account").status_code == 200
    assert password not in login.text and secret not in login.text
    session = client.cookies.get("cofrap_session")
    assert client.post("/web/logout", headers=headers).status_code == 200
    assert not client.cookies.get("cofrap_session")
    assert client.get("/api/me", headers=bearer(session)).status_code == 401


def test_web_errors_keep_the_current_form_and_never_echo_password(client):
    headers = csrf(client)
    response = client.post(
        "/web/login",
        data={
            "username": "missing",
            "password": "PRIVATE_PASSWORD",
            "code": "123456",
        },
        headers=headers,
    )
    assert response.status_code == 401
    assert response.headers["HX-Retarget"] == "#feedback"
    assert "PRIVATE_PASSWORD" not in response.text
    assert "Identifiants invalides" in response.text
    invalid = client.post("/web/login", data={"password": "PRIVATE_PASSWORD"}, headers=headers)
    assert invalid.status_code == 422
    assert invalid.headers["HX-Retarget"] == "#feedback"
    assert "PRIVATE_PASSWORD" not in invalid.text


def test_csrf_and_cross_origin_writes_are_rejected(client):
    assert client.post("/web/register", data={"username": "alice"}).status_code == 403
    headers = csrf(client)
    headers["Origin"] = "https://attacker.example"
    assert (
        client.post("/web/register", data={"username": "alice"}, headers=headers).status_code == 403
    )
    assert client.post("/api/users", json={"username": "alice"}, headers=headers).status_code == 403


def test_delivery_get_is_harmless_and_secrets_are_not_in_page(client):
    registration = register(client)
    response = client.get("/delivery")
    assert response.status_code == 200
    assert registration["enrollment_token"] not in response.text
    token = urlsplit(registration["delivery_url"]).fragment
    assert token not in response.text
    assert client.post("/api/password-deliveries/redeem", json={"token": token}).status_code == 200


def test_response_security_headers_and_local_assets(client):
    for path in ("/", "/login", "/api/me"):
        response = client.get(path)
        assert response.headers["Cache-Control"] == "no-store"
        assert response.headers["Referrer-Policy"] == "no-referrer"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "script-src 'self'" in response.headers["Content-Security-Policy"]
    assert 'lang="fr"' in client.get("/").text
    assert client.get("/static/htmx.min.js").status_code == 200
    assert client.get("/static/app.css").status_code == 200
    assert client.get("/docs").status_code == 200


def test_html_expiry_offers_and_authorizes_renewal(client, clock):
    password, secret = activate(client, clock)
    clock.advance(200 * 24 * 3600)
    headers = csrf(client)
    response = client.post(
        "/web/login",
        data={
            "username": "alice",
            "password": password,
            "code": pyotp.TOTP(secret).at(clock()),
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert "RENOUVELLEMENT NÉCESSAIRE" in response.text
    assert client.cookies.get("cofrap_renewal")
    assert not client.cookies.get("cofrap_session")
    renewed = client.post("/web/renew", headers=headers)
    assert renewed.status_code == 200
    assert "Un accès rien qu’à vous" in renewed.text
    assert not client.cookies.get("cofrap_renewal")
    assert client.cookies.get("cofrap_enrollment")
