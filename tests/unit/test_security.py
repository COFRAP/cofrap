import string
from datetime import UTC, datetime

import pyotp
import pytest
from cryptography.fernet import Fernet

from cofrap.domain.models import six_months_after
from cofrap.infrastructure.security import CryptoSecurity


@pytest.fixture(scope="module")
def security():
    return CryptoSecurity(Fernet.generate_key().decode())


def test_passwords_always_meet_requirements(security):
    passwords = {security.generate_password() for _ in range(1000)}
    assert len(passwords) == 1000
    for password in passwords:
        assert len(password) == 24
        for category in (
            string.ascii_uppercase,
            string.ascii_lowercase,
            string.digits,
            "!@#$%&*+-=?_",
        ):
            assert set(password) & set(category)


def test_hash_and_encryption_have_distinct_roles(security):
    password = security.generate_password()
    password_hash = security.hash_password(password)
    assert password_hash.startswith("$argon2id$")
    assert security.verify_password(password_hash, password)
    assert not security.verify_password(password_hash, "wrong")
    secret = security.totp_secret()
    encrypted = security.encrypt(secret)
    assert secret not in encrypted
    assert security.decrypt(encrypted) == secret


@pytest.mark.parametrize(
    ("date", "expected"),
    [("2026-08-31", "2027-02-28"), ("2023-08-31", "2024-02-29"), ("2026-03-05", "2026-09-05")],
)
def test_six_calendar_months(date, expected):
    value = datetime.fromisoformat(date).replace(tzinfo=UTC)
    assert six_months_after(value).date().isoformat() == expected


def test_totp_replay_and_drift(security):
    now = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
    secret = security.totp_secret()
    step = int(now.timestamp()) // 30
    code = pyotp.TOTP(secret).at(now)
    assert security.verify_totp(secret, code, now, None) == step
    assert security.verify_totp(secret, code, now, step) is None
    assert (
        security.verify_totp(secret, pyotp.TOTP(secret).at((step - 1) * 30), now, None) == step - 1
    )
    assert security.verify_totp(secret, pyotp.TOTP(secret).at((step - 2) * 30), now, None) is None
