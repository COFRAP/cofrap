import pytest
from sqlalchemy import select
from test_identity import activate, register

from cofrap.infrastructure.database import UserRow
from cofrap.infrastructure.maintenance import purge_expired_capabilities

pytestmark = pytest.mark.integration


def test_purge_removes_only_expired_capabilities(client, clock, database):
    activate(client, clock, username="active")
    register(client, username="expired")
    clock.advance(15 * 60)
    register(client, username="pending")
    with database.begin() as session:
        active = session.scalar(select(UserRow).where(UserRow.username == "active"))
        active_hash, active_totp = active.password_hash, active.totp_ciphertext
        assert purge_expired_capabilities(session, clock()) == 2
    with database() as session:
        users = {user.username: user for user in session.scalars(select(UserRow))}
        assert len(users) == 3
        assert users["expired"].delivery_ciphertext is None
        assert users["expired"].enrollment_digest is None
        assert users["expired"].password_hash.startswith("$argon2id$")
        assert users["pending"].delivery_ciphertext is not None
        assert users["active"].password_hash == active_hash
        assert users["active"].totp_ciphertext == active_totp
