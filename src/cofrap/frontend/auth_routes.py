from fastapi import APIRouter, Depends, Response

from cofrap.contracts import AuthResponse, LoginRequest, UserResponse
from cofrap.frontend import dependencies
from cofrap.frontend.openfaas_client import AuthenticationClient

router = APIRouter(prefix="/api", tags=["Authentification"])


@router.post("/auth/login", response_model=AuthResponse)
def login(data: LoginRequest, service: AuthenticationClient = Depends(dependencies.authentication)):
    return service.authenticate(data.username, data.password.get_secret_value(), data.code)


@router.get("/me", response_model=UserResponse)
def me(
    token: str = Depends(dependencies.token),
    service: AuthenticationClient = Depends(dependencies.authentication),
):
    return service.current_user(token)


@router.post("/auth/logout", status_code=204)
def logout(
    token: str = Depends(dependencies.token),
    service: AuthenticationClient = Depends(dependencies.authentication),
):
    service.logout(token)
    return Response(status_code=204)
