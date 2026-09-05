from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from cofrap.domain.models import User


@dataclass(frozen=True)
class UserInfo:
    id: UUID
    username: str
    generated_at: datetime | None
    expires_at: datetime | None
    mfa_confirmed: bool
    expired: bool

    @classmethod
    def from_user(cls, user: User) -> "UserInfo":
        return cls(
            user.id,
            user.username,
            user.generated_at,
            user.expires_at,
            user.mfa_confirmed,
            user.expired,
        )


@dataclass(frozen=True)
class Enrollment:
    user: UserInfo
    enrollment_token: str
    delivery_token: str
    expires_at: datetime


@dataclass(frozen=True)
class PasswordDelivery:
    username: str
    password: str


@dataclass(frozen=True)
class TotpSetup:
    username: str
    secret: str
    provisioning_uri: str


@dataclass(frozen=True)
class Authentication:
    status: Literal["authenticated", "renewal_required"]
    token: str
    expires_at: datetime
    user: UserInfo
