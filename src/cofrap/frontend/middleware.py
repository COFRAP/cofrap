import secrets

from fastapi import Request
from fastapi.responses import JSONResponse

from cofrap.frontend.rendering import fragment


async def browser_security(request: Request, call_next):
    settings = request.app.state.settings
    csrf = request.cookies.get("cofrap_csrf", "")
    request.state.csrf = csrf or secrets.token_urlsafe(32)
    unsafe = request.method not in {"GET", "HEAD", "OPTIONS"}
    origin = request.headers.get("origin")
    expected_origin = str(settings.public_base_url).rstrip("/")
    origin_invalid = unsafe and origin is not None and origin != expected_origin
    csrf_invalid = (
        unsafe
        and request.url.path.startswith("/web/")
        and (
            not csrf
            or not secrets.compare_digest(
                csrf.encode(), request.headers.get("x-csrf-token", "").encode()
            )
        )
    )
    if origin_invalid or csrf_invalid:
        if request.url.path.startswith("/web/"):
            response = fragment(
                request, "error", message="Session du formulaire expirée. Rechargez la page."
            )
            response.status_code = 403
            response.headers.update({"HX-Retarget": "#feedback", "HX-Reswap": "innerHTML"})
        else:
            response = JSONResponse(
                {"error": {"code": "forbidden", "message": "Requête refusée."}}, 403
            )
    else:
        response = await call_next(request)
    if not csrf:
        response.set_cookie(
            "cofrap_csrf",
            request.state.csrf,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="strict",
            path="/",
        )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path not in {"/docs", "/redoc", "/docs/oauth2-redirect"}:
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
    return response
