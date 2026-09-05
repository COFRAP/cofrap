from collections.abc import Callable

from cofrap.application.capabilities import RENEWAL_TTL, SESSION_TTL, authorize, issue, revoke
from cofrap.application.ports import Clock, Security, UnitOfWork
from cofrap.application.results import Authentication, UserInfo
from cofrap.domain.errors import CredentialsExpired, InvalidCredentials


class AuthenticationService:
    def __init__(self, uow: Callable[[], UnitOfWork], security: Security, clock: Clock):
        self.uow = uow
        self.security = security
        self.clock = clock

    def authenticate(self, username: str, password: str, code: str) -> Authentication:
        now = self.clock()
        with self.uow() as uow:
            user = uow.users.by_username(username)
            password_ok = self.security.verify_password(
                user.password_hash if user else "", password
            )
            if not user or not password_ok or not user.mfa_confirmed:
                raise InvalidCredentials()
            step = self.security.verify_totp(
                self.security.decrypt(user.totp_ciphertext), code, now, user.last_totp_step
            )
            if step is None:
                raise InvalidCredentials()
            user.last_totp_step = step
            if user.credentials_expired(now):
                user.expired = True
                revoke(user, "session")
                expiry = now + RENEWAL_TTL
                token = issue(user, "renewal", self.security, expiry)
                status = "renewal_required"
            else:
                expiry = min(now + SESSION_TTL, user.expires_at)
                token = issue(user, "session", self.security, expiry)
                status = "authenticated"
            uow.users.save(user)
        return Authentication(status, token, expiry, UserInfo.from_user(user))

    def current_user(self, token: str) -> UserInfo:
        with self.uow() as uow:
            user = authorize(uow.users, self.security, "session", token, self.clock())
            expired = user.credentials_expired(self.clock())
            if expired:
                user.expired = True
                revoke(user, "session")
                uow.users.save(user)
        if expired:
            raise CredentialsExpired()
        return UserInfo.from_user(user)

    def logout(self, token: str) -> None:
        with self.uow() as uow:
            user = authorize(uow.users, self.security, "session", token, self.clock())
            revoke(user, "session")
            uow.users.save(user)
