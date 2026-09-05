from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from cofrap.application.authentication import AuthenticationService
from cofrap.application.enrollment import EnrollmentService
from cofrap.domain.errors import DomainError
from cofrap.infrastructure.database import create_session_factory
from cofrap.infrastructure.repositories import SqlUnitOfWork
from cofrap.infrastructure.security import CryptoSecurity
from cofrap.infrastructure.settings import Settings, get_settings
from cofrap.presentation import auth_routes, enrollment_routes, errors, health_routes


def create_app(settings: Settings | None = None, clock=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        config = settings or get_settings()
        engine, sessions = create_session_factory(config)
        security = CryptoSecurity(config.encryption_key.get_secret_value())
        now = clock or (lambda: datetime.now(UTC))

        def uow():
            return SqlUnitOfWork(sessions)

        app.state.settings = config
        app.state.engine = engine
        app.state.enrollment = EnrollmentService(uow, security, now)
        app.state.authentication = AuthenticationService(uow, security, now)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="COFRAP — Identité sécurisée", version="0.1.0", lifespan=lifespan)
    app.add_exception_handler(DomainError, errors.domain_error)
    app.add_exception_handler(RequestValidationError, errors.validation_error)
    app.include_router(health_routes.router)
    app.include_router(enrollment_routes.router)
    app.include_router(auth_routes.router)
    return app


app = create_app()
