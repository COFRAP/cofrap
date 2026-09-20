import pyotp
import pytest

from cofrap.domain.errors import EnrollmentRequired, InvalidCredentials, InvalidToken


def test_setup_returns_same_secret_until_confirmation(services, enrollment):
    services.password.redeem_password(enrollment.delivery_token)

    result = services.totp.setup_totp(enrollment.enrollment_token)
    repeated = services.totp.setup_totp(enrollment.enrollment_token)

    assert result.username == "alice"
    assert result.secret == repeated.secret
    assert pyotp.parse_uri(result.provisioning_uri).secret == result.secret
    user = services.users.by_username("alice")
    assert user.totp_ciphertext != result.secret
    assert services.security.decrypt(user.totp_ciphertext) == result.secret


def test_setup_requires_password_delivery(services, enrollment):
    with pytest.raises(EnrollmentRequired):
        services.totp.setup_totp(enrollment.enrollment_token)

    assert services.users.by_username("alice").totp_ciphertext is None


def test_confirm_requires_setup(services, enrollment):
    services.password.redeem_password(enrollment.delivery_token)

    with pytest.raises(EnrollmentRequired):
        services.totp.confirm_totp(enrollment.enrollment_token, "123456")


def test_confirm_activates_mfa_and_consumes_enrollment(services, enrollment):
    services.password.redeem_password(enrollment.delivery_token)
    setup = services.totp.setup_totp(enrollment.enrollment_token)
    code = pyotp.TOTP(setup.secret).at(services.clock.now)

    result = services.totp.confirm_totp(enrollment.enrollment_token, code)

    assert result.mfa_confirmed
    assert result.generated_at == services.clock.now
    assert not result.expired
    assert services.users.by_username("alice").enrollment_digest is None
    with pytest.raises(InvalidToken):
        services.totp.confirm_totp(enrollment.enrollment_token, code)


def test_confirm_rejects_wrong_code(services, enrollment):
    services.password.redeem_password(enrollment.delivery_token)
    services.totp.setup_totp(enrollment.enrollment_token)

    # Longueur volontairement différente : ce code ne peut jamais être valide.
    with pytest.raises(InvalidCredentials):
        services.totp.confirm_totp(enrollment.enrollment_token, "0000000")

    user = services.users.by_username("alice")
    assert not user.mfa_confirmed
    assert user.generated_at is None
    assert user.enrollment_digest is not None


def test_setup_rejects_expired_enrollment(services, enrollment):
    services.password.redeem_password(enrollment.delivery_token)
    services.clock.now = enrollment.expires_at

    with pytest.raises(InvalidToken):
        services.totp.setup_totp(enrollment.enrollment_token)


@pytest.mark.parametrize("token", ["", "unknown-token"])
def test_setup_rejects_invalid_token(services, token):
    with pytest.raises(InvalidToken):
        services.totp.setup_totp(token)
