from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from cofrap.domain.errors import BackendUnavailable

router = APIRouter(tags=["Santé"])


@router.get("/health/live")
def live():
    return {"status": "ok"}


@router.get("/health/ready")
def ready(request: Request):
    try:
        request.app.state.gateway.ready()
    except BackendUnavailable:
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ok", "database": "postgresql", "backend": "openfaas"}
