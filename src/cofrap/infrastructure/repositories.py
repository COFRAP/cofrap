from dataclasses import asdict, fields

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cofrap.application.ports import TokenPurpose
from cofrap.domain.errors import UsernameTaken
from cofrap.domain.models import User
from cofrap.infrastructure.database import UserRow


class SqlUserRepository:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _to_domain(row: UserRow | None) -> User | None:
        return (
            User(**{field.name: getattr(row, field.name) for field in fields(User)})
            if row
            else None
        )

    def by_username(self, username: str) -> User | None:
        row = self.session.scalar(
            select(UserRow).where(UserRow.username == username).with_for_update()
        )
        return self._to_domain(row)

    def by_token(self, purpose: TokenPurpose, digest: str) -> User | None:
        column = getattr(UserRow, f"{purpose}_digest")
        row = self.session.scalar(select(UserRow).where(column == digest).with_for_update())
        return self._to_domain(row)

    def add(self, user: User) -> None:
        self.session.add(UserRow(**asdict(user)))
        try:
            self.session.flush()
        except IntegrityError as exc:
            # Le nom de la contrainte est celui créé par PostgreSQL dans la migration.
            if (
                getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
                == "users_username_key"
            ):
                raise UsernameTaken() from exc
            raise

    def save(self, user: User) -> None:
        row = self.session.get(UserRow, user.id)
        if row is None:
            raise RuntimeError("L’utilisateur doit exister avant sa mise à jour.")
        for name, value in asdict(user).items():
            setattr(row, name, value)


class SqlUnitOfWork:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def __enter__(self):
        self.session = self.session_factory()
        self.users = SqlUserRepository(self.session)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            if exc_type is None:
                self.session.commit()
            else:
                self.session.rollback()
        finally:
            self.session.close()
