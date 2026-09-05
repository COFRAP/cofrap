import calendar
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


def six_months_after(value: datetime) -> datetime:
    """Six mois calendaires, avec rabattement au dernier jour du mois cible."""
    month_index = value.year * 12 + value.month - 1 + 6
    year, month = divmod(month_index, 12)
    month += 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


@dataclass
class User:
    id: UUID
    username: str
    password_hash: str
    created_at: datetime
    generated_at: datetime | None = None
    expired: bool = False
    mfa_confirmed: bool = False
    totp_ciphertext: str | None = None
    last_totp_step: int | None = None
    delivery_ciphertext: str | None = None
    delivery_digest: str | None = None
    delivery_expires_at: datetime | None = None
    enrollment_digest: str | None = None
    enrollment_expires_at: datetime | None = None
    renewal_digest: str | None = None
    renewal_expires_at: datetime | None = None
    session_digest: str | None = None
    session_expires_at: datetime | None = None

    def credentials_expired(self, now: datetime) -> bool:
        return self.expired or (
            self.generated_at is not None and now >= six_months_after(self.generated_at)
        )

    @property
    def expires_at(self) -> datetime | None:
        return six_months_after(self.generated_at) if self.generated_at else None
