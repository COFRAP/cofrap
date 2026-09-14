from collections.abc import Callable

from cofrap.application.capabilities import authorize, revoke
from cofrap.application.ports import Clock, Security, UnitOfWork
from cofrap.application.results import TotpSetup, UserInfo
from cofrap.domain.errors import EnrollmentRequired, InvalidCredentials


class TotpService:
    def __init__(self, uow: Callable[[], UnitOfWork], security: Security, clock: Clock):
        self.uow = uow
        self.security = security
        self.clock = clock

    def setup_totp(self, token: str) -> TotpSetup:
        with self.uow() as uow:
            user = authorize(uow.users, self.security, "enrollment", token, self.clock())
            if user.delivery_digest is not None:
                raise EnrollmentRequired()
            if user.totp_ciphertext is None:
                user.totp_ciphertext = self.security.encrypt(self.security.totp_secret())
                uow.users.save(user)
            secret = self.security.decrypt(user.totp_ciphertext)
        return TotpSetup(
            user.username, secret, self.security.provisioning_uri(secret, user.username)
        )

    def confirm_totp(self, token: str, code: str) -> UserInfo:
        with self.uow() as uow:
            user = authorize(uow.users, self.security, "enrollment", token, self.clock())
            if user.delivery_digest is not None or user.totp_ciphertext is None:
                raise EnrollmentRequired()
            step = self.security.verify_totp(
                self.security.decrypt(user.totp_ciphertext), code, self.clock(), user.last_totp_step
            )
            if step is None:
                raise InvalidCredentials()
            user.last_totp_step = step
            user.mfa_confirmed = True
            user.generated_at = self.clock()
            user.expired = False
            revoke(user, "enrollment")
            uow.users.save(user)
        return UserInfo.from_user(user)
