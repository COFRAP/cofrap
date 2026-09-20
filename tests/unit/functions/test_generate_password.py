import pytest

from cofrap.domain.errors import InvalidToken, UsernameTaken


def test_register_generates_password_and_enrollment(services):
    result = services.password.register("alice")
    user = services.users.by_username("alice")
    password = services.security.decrypt(user.delivery_ciphertext)

    assert result.user.username == "alice"
    assert not result.user.mfa_confirmed
    assert len(password) == 24
    assert services.security.verify_password(user.password_hash, password)
    assert user.password_hash != password
    assert user.delivery_ciphertext != password
    assert result.enrollment_token != result.delivery_token
    assert result.expires_at > services.clock.now


def test_register_rejects_duplicate_username(services, enrollment):
    with pytest.raises(UsernameTaken):
        services.password.register("alice")

    assert len(services.users.users) == 1
    assert services.password.inspect(enrollment.enrollment_token)[0] == enrollment.user


def test_password_can_only_be_redeemed_once(services, enrollment):
    assert services.password.inspect(enrollment.enrollment_token)[1] is False

    result = services.password.redeem_password(enrollment.delivery_token)

    user = services.users.by_username("alice")
    assert result.username == "alice"
    assert services.security.verify_password(user.password_hash, result.password)
    assert user.delivery_ciphertext is None
    assert user.delivery_digest is None
    assert services.password.inspect(enrollment.enrollment_token)[1] is True
    with pytest.raises(InvalidToken):
        services.password.redeem_password(enrollment.delivery_token)


@pytest.mark.parametrize("token", ["", "unknown-token"])
def test_redeem_rejects_invalid_token(services, token):
    with pytest.raises(InvalidToken):
        services.password.redeem_password(token)


def test_redeem_rejects_expired_token(services, enrollment):
    services.clock.now = enrollment.expires_at

    with pytest.raises(InvalidToken):
        services.password.redeem_password(enrollment.delivery_token)

    assert services.users.by_username("alice").delivery_ciphertext is not None


def test_renew_rejects_enrollment_token(services, enrollment):
    with pytest.raises(InvalidToken):
        services.password.renew(enrollment.enrollment_token)
