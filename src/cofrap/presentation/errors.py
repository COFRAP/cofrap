from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from cofrap.domain.errors import (
    CredentialsExpired,
    DomainError,
    EnrollmentRequired,
    InvalidCredentials,
    InvalidToken,
    UsernameTaken,
)

STATUSES = {
    UsernameTaken: 409,
    InvalidCredentials: 401,
    InvalidToken: 401,
    EnrollmentRequired: 409,
    CredentialsExpired: 403,
}


async def domain_error(request: Request, exc: DomainError):
    return JSONResponse(
        {"error": {"code": exc.code, "message": exc.message}},
        status_code=STATUSES.get(type(exc), 400),
    )


async def validation_error(request: Request, exc: RequestValidationError):
    # Ne jamais recopier input / ctx : ils peuvent contenir un mot de passe ou un jeton.
    return JSONResponse(
        {"error": {"code": "validation_error", "message": "Vérifiez les champs saisis."}},
        status_code=422,
    )
