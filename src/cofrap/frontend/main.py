from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from cofrap.domain.errors import DomainError
from cofrap.frontend import auth_routes, enrollment_routes, errors, health_routes, web_routes
from cofrap.frontend.middleware import browser_security
from cofrap.frontend.openfaas_client import AuthenticationClient, EnrollmentClient, OpenFaaSClient
from cofrap.frontend.rendering import PRESENTATION_ROOT
from cofrap.frontend.settings import FrontendSettings


def create_app(settings=None, *, transport: httpx.BaseTransport | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        config = settings or FrontendSettings()
        with httpx.Client(
            base_url=str(config.openfaas_gateway_url),
            timeout=config.openfaas_timeout,
            transport=transport,
        ) as http:
            gateway = OpenFaaSClient(http)
            app.state.settings = config
            app.state.gateway = gateway
            app.state.enrollment = EnrollmentClient(gateway)
            app.state.authentication = AuthenticationClient(gateway)
            yield

    app = FastAPI(title="COFRAP — Identité sécurisée", version="0.2.0", lifespan=lifespan)
    app.add_exception_handler(DomainError, errors.domain_error)
    app.add_exception_handler(RequestValidationError, errors.validation_error)
    app.middleware("http")(browser_security)
    app.include_router(health_routes.router)
    app.include_router(enrollment_routes.router)
    app.include_router(auth_routes.router)
    app.include_router(web_routes.router)
    app.mount("/static", StaticFiles(directory=PRESENTATION_ROOT / "static"), name="static")
    return app


app = create_app()
