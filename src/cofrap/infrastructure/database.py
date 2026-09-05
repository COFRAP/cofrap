from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from cofrap.infrastructure.settings import Settings


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired: Mapped[bool] = mapped_column(default=False)
    mfa_confirmed: Mapped[bool] = mapped_column(default=False)
    totp_ciphertext: Mapped[str | None] = mapped_column(Text)
    last_totp_step: Mapped[int | None]
    delivery_ciphertext: Mapped[str | None] = mapped_column(Text)
    delivery_digest: Mapped[str | None] = mapped_column(String(64), unique=True)
    delivery_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enrollment_digest: Mapped[str | None] = mapped_column(String(64), unique=True)
    enrollment_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    renewal_digest: Mapped[str | None] = mapped_column(String(64), unique=True)
    renewal_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_digest: Mapped[str | None] = mapped_column(String(64), unique=True)
    session_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def create_session_factory(settings: Settings):
    engine = create_engine(settings.database_url, pool_pre_ping=True, hide_parameters=True)
    return engine, sessionmaker(engine, expire_on_commit=False)
