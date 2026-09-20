import importlib
from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace

import pyotp
import pytest
from cryptography.fernet import Fernet

from cofrap.infrastructure.security import CryptoSecurity


class MemoryUsers:
    """Stockage minimal pour tester les services sans base de données."""

    def __init__(self):
        self.users = {}

    def by_username(self, username):
        return self.users.get(username)

    def by_token(self, purpose, digest):
        for user in self.users.values():
            if getattr(user, f"{purpose}_digest") == digest:
                return user
        return None

    def add(self, user):
        self.users[user.username] = user

    def save(self, user):
        self.users[user.username] = user


@pytest.fixture(scope="module")
def security():
    return CryptoSecurity(Fernet.generate_key().decode())


@pytest.fixture
def services(security):
    users = MemoryUsers()
    clock = SimpleNamespace(now=datetime(2026, 9, 5, 12, 0, tzinfo=UTC))

    @contextmanager
    def uow():
        yield SimpleNamespace(users=users)

    def service(function, name):
        module = importlib.import_module(f"functions.{function}.service")
        return getattr(module, name)(uow, security, lambda: clock.now)

    return SimpleNamespace(
        password=service("generate-password", "EnrollmentService"),
        totp=service("generate-2fa", "TotpService"),
        authentication=service("authenticate", "AuthenticationService"),
        users=users,
        security=security,
        clock=clock,
    )


@pytest.fixture
def enrollment(services):
    return services.password.register("alice")


@pytest.fixture
def activated(services, enrollment):
    delivery = services.password.redeem_password(enrollment.delivery_token)
    setup = services.totp.setup_totp(enrollment.enrollment_token)
    code = pyotp.TOTP(setup.secret).at(services.clock.now)
    services.totp.confirm_totp(enrollment.enrollment_token, code)
    return SimpleNamespace(password=delivery.password, secret=setup.secret)
