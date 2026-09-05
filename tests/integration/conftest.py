from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import text

from cofrap.infrastructure.database import create_session_factory
from cofrap.infrastructure.settings import Settings
from cofrap.main import create_app


@dataclass
class MutableClock:
    now: datetime = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)

    def __call__(self):
        return self.now

    def advance(self, seconds=30):
        self.now += timedelta(seconds=seconds)


@pytest.fixture(scope="session")
def settings():
    return Settings(
        _env_file=None,
        postgres_user="cofrap_test",
        postgres_password="local_test_only",
        postgres_db="cofrap_test",
        postgres_host="127.0.0.1",
        postgres_port=55433,
        encryption_key=Fernet.generate_key().decode(),
        public_base_url="http://testserver",
    )


@pytest.fixture(scope="session")
def database(settings):
    engine, sessions = create_session_factory(settings)
    # Garde-fou : ce fixture ne doit jamais vider la base de développement.
    assert engine.url.database == "cofrap_test" and engine.url.port == 55433
    with engine.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        command.check(config)
    yield sessions
    engine.dispose()


@pytest.fixture
def clock():
    return MutableClock()


@pytest.fixture
def client(settings, database, clock):
    with database() as session:
        session.execute(text("TRUNCATE TABLE users"))
        session.commit()
    with TestClient(create_app(settings, clock)) as client:
        yield client
