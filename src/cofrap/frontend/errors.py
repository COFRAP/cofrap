from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from cofrap.domain.errors import DomainError
from cofrap.frontend.rendering import fragment, page
from cofrap.http_errors import STATUSES


async def domain_error(request: Request, exc: DomainError):
    if not request.url.path.startswith("/api/"):
        return html_error(request, exc.message, STATUSES.get(type(exc), 400))
    return JSONResponse(
        {"error": {"code": exc.code, "message": exc.message}},
        status_code=STATUSES.get(type(exc), 400),
    )


async def validation_error(request: Request, exc: RequestValidationError):
    if request.url.path.startswith("/web/"):
        return html_error(
            request,
            "Vérifiez les champs : identifiant de 3 à 64 caractères (lettres, chiffres, . _ -), "
            "mot de passe et code à 6 chiffres selon le formulaire.",
            422,
        )
    # Ne jamais recopier input / ctx : ils peuvent contenir un mot de passe ou un jeton.
    return JSONResponse(
        {"error": {"code": "validation_error", "message": "Vérifiez les champs saisis."}},
        status_code=422,
    )


def html_error(request: Request, message: str, status: int):
    if request.url.path.startswith("/web/"):
        response = fragment(request, "error", message=message)
        response.headers.update({"HX-Retarget": "#feedback", "HX-Reswap": "innerHTML"})
    else:
        response = page(request, "unavailable", message=message)
    response.status_code = status
    return response
