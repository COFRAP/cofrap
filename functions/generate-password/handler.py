from dataclasses import replace

from fastapi import APIRouter, Request

from cofrap.contracts import RegisterRequest, TokenRequest
from cofrap.function_runtime import create_function_app
from cofrap.infrastructure.qr import qr_data_url

from .service import EnrollmentService

router = APIRouter()


def delivery_view(request, token):
    url = f"{str(request.app.state.settings.public_base_url).rstrip('/')}/delivery#{token}"
    return {"delivery_url": url, "delivery_qr": qr_data_url(url)}


@router.post("/register")
def register(data: RegisterRequest, request: Request):
    result = request.app.state.service.register(data.username)
    return replace(result, **delivery_view(request, result.delivery_token))


@router.post("/renew")
def renew(data: TokenRequest, request: Request):
    result = request.app.state.service.renew(data.token)
    return replace(result, **delivery_view(request, result.delivery_token))


@router.post("/redeem")
def redeem(data: TokenRequest, request: Request):
    return request.app.state.service.redeem_password(data.token)


@router.post("/inspect")
def inspect(data: TokenRequest, request: Request):
    user, redeemed = request.app.state.service.inspect(data.token)
    return {"user": user, "redeemed": redeemed}


@router.post("/qr")
def qr(data: TokenRequest, request: Request):
    # Rendering a link does not consume or grant its one-use capability.
    return delivery_view(request, data.token)


def create_app(settings=None, clock=None):
    return create_function_app(EnrollmentService, router, settings, clock)


app = create_app()
