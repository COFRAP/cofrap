from dataclasses import replace

from fastapi import APIRouter, Request

from cofrap.contracts import TokenRequest, TotpCode
from cofrap.function_runtime import create_function_app
from cofrap.infrastructure.qr import qr_data_url

from .service import TotpService

router = APIRouter()


class Confirmation(TokenRequest):
    code: TotpCode


@router.post("/setup")
def setup(data: TokenRequest, request: Request):
    result = request.app.state.service.setup_totp(data.token)
    return replace(result, qr=qr_data_url(result.provisioning_uri))


@router.post("/confirm")
def confirm(data: Confirmation, request: Request):
    return request.app.state.service.confirm_totp(data.token, data.code)


def create_app(settings=None, clock=None):
    return create_function_app(TotpService, router, settings, clock)


app = create_app()
