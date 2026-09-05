from datetime import datetime, timedelta

from cofrap.application.ports import Security, TokenPurpose, UserRepository
from cofrap.domain.errors import InvalidToken
from cofrap.domain.models import User

ENROLLMENT_TTL = timedelta(minutes=15)
RENEWAL_TTL = timedelta(minutes=5)
SESSION_TTL = timedelta(minutes=30)


def issue(user: User, purpose: TokenPurpose, security: Security, expires_at: datetime) -> str:
    token = security.token()
    setattr(user, f"{purpose}_digest", security.digest(token))
    setattr(user, f"{purpose}_expires_at", expires_at)
    return token


def revoke(user: User, purpose: TokenPurpose) -> None:
    setattr(user, f"{purpose}_digest", None)
    setattr(user, f"{purpose}_expires_at", None)


def authorize(
    users: UserRepository, security: Security, purpose: TokenPurpose, token: str, now: datetime
) -> User:
    if not token:
        raise InvalidToken()
    user = users.by_token(purpose, security.digest(token))
    expiry = getattr(user, f"{purpose}_expires_at", None)
    if user is None or expiry is None or now >= expiry:
        raise InvalidToken()
    return user
