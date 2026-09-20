from datetime import timedelta

import pyotp
import pytest

from cofrap.domain.errors import CredentialsExpired, InvalidCredentials, InvalidToken


@pytest.fixture
def login(services, activated):
    # Le code utilisé pour activer la 2FA ne doit pas être réutilisé.
    services.clock.now += timedelta(seconds=30)
    return {
        "username": "alice",
        "password": activated.password,
        "code": pyotp.TOTP(activated.secret).at(services.clock.now),
    }


def test_login_current_user_and_logout(services, login):
    result = services.authentication.authenticate(**login)

    assert result.status == "authenticated"
    assert result.expires_at == services.clock.now + timedelta(minutes=30)
    assert services.authentication.current_user(result.token).username == "alice"

    services.authentication.logout(result.token)

    with pytest.raises(InvalidToken):
        services.authentication.current_user(result.token)


@pytest.mark.parametrize(
    ("field", "value"),
    [("username", "unknown"), ("password", "wrong-password"), ("code", "0000000")],
)
def test_login_rejects_invalid_credentials(services, login, field, value):
    login[field] = value
    user = services.users.by_username("alice")
    previous_step = user.last_totp_step

    with pytest.raises(InvalidCredentials):
        services.authentication.authenticate(**login)

    assert user.session_digest is None
    assert user.last_totp_step == previous_step


def test_login_requires_confirmed_mfa(services, enrollment):
    delivery = services.password.redeem_password(enrollment.delivery_token)

    with pytest.raises(InvalidCredentials):
        services.authentication.authenticate("alice", delivery.password, "123456")


def test_login_rejects_reused_totp(services, login):
    result = services.authentication.authenticate(**login)

    with pytest.raises(InvalidCredentials):
        services.authentication.authenticate(**login)

    assert services.authentication.current_user(result.token).username == "alice"


def test_session_expires(services, login):
    result = services.authentication.authenticate(**login)
    services.clock.now = result.expires_at

    with pytest.raises(InvalidToken):
        services.authentication.current_user(result.token)


def test_current_user_rejects_expired_credentials(services, login):
    result = services.authentication.authenticate(**login)
    user = services.users.by_username("alice")
    user.expired = True

    with pytest.raises(CredentialsExpired):
        services.authentication.current_user(result.token)

    assert user.session_digest is None


def test_expired_credentials_allow_one_renewal(services, activated, login):
    services.authentication.authenticate(**login)
    user = services.users.by_username("alice")
    services.clock.now = user.expires_at
    login["code"] = pyotp.TOTP(activated.secret).at(services.clock.now)

    result = services.authentication.authenticate(**login)

    assert result.status == "renewal_required"
    assert result.expires_at == services.clock.now + timedelta(minutes=5)
    assert user.expired
    assert user.session_digest is None
    with pytest.raises(InvalidToken):
        services.authentication.current_user(result.token)

    renewed = services.password.renew(result.token)
    delivery = services.password.redeem_password(renewed.delivery_token)

    assert delivery.password != activated.password
    assert not user.mfa_confirmed
    assert user.totp_ciphertext is None
    assert user.generated_at is None
    assert user.last_totp_step is None
    assert not services.security.verify_password(user.password_hash, activated.password)
    with pytest.raises(InvalidToken):
        services.password.renew(result.token)


@pytest.mark.parametrize("operation", ["current_user", "logout"])
def test_session_operations_reject_unknown_token(services, operation):
    with pytest.raises(InvalidToken):
        getattr(services.authentication, operation)("unknown-token")
