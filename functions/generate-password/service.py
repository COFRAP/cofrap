from collections.abc import Callable
from uuid import uuid4

from cofrap.application.capabilities import ENROLLMENT_TTL, authorize, issue, revoke
from cofrap.application.ports import Clock, Security, UnitOfWork
from cofrap.application.results import Enrollment, PasswordDelivery, UserInfo
from cofrap.domain.errors import UsernameTaken
from cofrap.domain.models import User


class EnrollmentService:
    def __init__(self, uow: Callable[[], UnitOfWork], security: Security, clock: Clock):
        self.uow = uow
        self.security = security
        self.clock = clock

    def _prepare(self, user: User) -> Enrollment:
        password = self.security.generate_password()
        user.password_hash = self.security.hash_password(password)
        user.delivery_ciphertext = self.security.encrypt(password)
        user.totp_ciphertext = None
        user.last_totp_step = None
        user.mfa_confirmed = False
        user.generated_at = None
        expires_at = self.clock() + ENROLLMENT_TTL
        for purpose in ("session", "renewal"):
            revoke(user, purpose)
        enrollment_token = issue(user, "enrollment", self.security, expires_at)
        delivery_token = issue(user, "delivery", self.security, expires_at)
        return Enrollment(UserInfo.from_user(user), enrollment_token, delivery_token, expires_at)

    def register(self, username: str) -> Enrollment:
        with self.uow() as uow:
            if uow.users.by_username(username):
                raise UsernameTaken()
            user = User(uuid4(), username, "", self.clock())
            result = self._prepare(user)
            uow.users.add(user)
        return result

    def redeem_password(self, token: str) -> PasswordDelivery:
        with self.uow() as uow:
            user = authorize(uow.users, self.security, "delivery", token, self.clock())
            password = self.security.decrypt(user.delivery_ciphertext)
            user.delivery_ciphertext = None
            revoke(user, "delivery")
            uow.users.save(user)
        return PasswordDelivery(user.username, password)

    def inspect(self, token: str) -> tuple[UserInfo, bool]:
        with self.uow() as uow:
            user = authorize(uow.users, self.security, "enrollment", token, self.clock())
            return UserInfo.from_user(user), user.delivery_digest is None

    def renew(self, token: str) -> Enrollment:
        with self.uow() as uow:
            user = authorize(uow.users, self.security, "renewal", token, self.clock())
            result = self._prepare(user)
            uow.users.save(user)
        return result
