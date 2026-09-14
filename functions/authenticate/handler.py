from fastapi import APIRouter, Request, Response

from cofrap.contracts import LoginRequest, TokenRequest
from cofrap.function_runtime import create_function_app

from .service import AuthenticationService

router = APIRouter()


@router.post("/login")
def login(data: LoginRequest, request: Request):
    return request.app.state.service.authenticate(
        data.username, data.password.get_secret_value(), data.code
    )


@router.post("/me")
def me(data: TokenRequest, request: Request):
    return request.app.state.service.current_user(data.token)


@router.post("/logout", status_code=204)
def logout(data: TokenRequest, request: Request):
    request.app.state.service.logout(data.token)
    return Response(status_code=204)


def create_app(settings=None, clock=None):
    return create_function_app(AuthenticationService, router, settings, clock)


app = create_app()
