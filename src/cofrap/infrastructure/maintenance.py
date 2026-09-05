"""Purge les capacités expirées sans supprimer les utilisateurs."""

from datetime import UTC, datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from cofrap.infrastructure.database import UserRow, create_session_factory
from cofrap.infrastructure.settings import get_settings


def purge_expired_capabilities(session: Session, now: datetime) -> int:
    count = 0
    for purpose in ("delivery", "enrollment", "renewal", "session"):
        expiry = getattr(UserRow, f"{purpose}_expires_at")
        values = {f"{purpose}_digest": None, f"{purpose}_expires_at": None}
        if purpose == "delivery":
            values["delivery_ciphertext"] = None
        result = session.execute(update(UserRow).where(expiry <= now).values(**values))
        count += result.rowcount
    return count


def main():
    engine, sessions = create_session_factory(get_settings())
    try:
        with sessions.begin() as session:
            count = purge_expired_capabilities(session, datetime.now(UTC))
        print(f"{count} capacité(s) expirée(s) purgée(s). Aucun utilisateur supprimé.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
