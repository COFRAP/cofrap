"""HTTP runtime shared by independently deployed OpenFaaS functions."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from cofrap.domain.errors import DomainError
from cofrap.http_errors import STATUSES
from cofrap.infrastructure.database import create_session_factory
from cofrap.infrastructure.repositories import SqlUnitOfWork
from cofrap.infrastructure.security import CryptoSecurity
from cofrap.infrastructure.settings import get_settings


def create_function_app(service_type, router: APIRouter, settings=None, clock=None):
    @asynccontextmanager
    async def lifespan(app):
        config = settings or get_settings()
        engine, sessions = create_session_factory(config)
        app.state.settings = config
        app.state.engine = engine
        app.state.service = service_type(
            lambda: SqlUnitOfWork(sessions),
            CryptoSecurity(config.encryption_key.get_secret_value()),
            clock or (lambda: datetime.now(UTC)),
        )
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
    app.include_router(router)

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse(
            {"error": {"code": exc.code, "message": exc.message}},
            status_code=STATUSES.get(type(exc), 400),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(
            {"error": {"code": "validation_error", "message": "Vérifiez les champs saisis."}},
            status_code=422,
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse(
            {"error": {"code": "backend_unavailable", "message": "Service indisponible."}},
            status_code=503,
        )

    @app.middleware("http")
    async def private_response(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/health/ready")
    def ready(request: Request):
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM users LIMIT 1"))
        return {"status": "ok", "database": "postgresql"}

    return app
