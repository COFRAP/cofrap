from fastapi import APIRouter, Depends, Request

from cofrap.application.results import Enrollment
from cofrap.contracts import (
    ConfirmRequest,
    EnrollmentResponse,
    PasswordResponse,
    RegisterRequest,
    TokenRequest,
    TotpResponse,
    UserResponse,
)
from cofrap.frontend import dependencies
from cofrap.frontend.openfaas_client import EnrollmentClient

router = APIRouter(prefix="/api", tags=["Inscription et renouvellement"])


def present_enrollment(result: Enrollment) -> EnrollmentResponse:
    return EnrollmentResponse(
        user=UserResponse.model_validate(result.user),
        enrollment_token=result.enrollment_token,
        delivery_url=result.delivery_url,
        delivery_qr=result.delivery_qr,
        expires_at=result.expires_at,
    )


@router.post("/users", response_model=EnrollmentResponse, status_code=201)
def register(
    data: RegisterRequest,
    request: Request,
    service: EnrollmentClient = Depends(dependencies.enrollment),
):
    return present_enrollment(service.register(data.username))


@router.post("/password-deliveries/redeem", response_model=PasswordResponse)
def redeem(data: TokenRequest, service: EnrollmentClient = Depends(dependencies.enrollment)):
    return service.redeem_password(data.token)


@router.post("/enrollment/totp", response_model=TotpResponse)
def setup(
    token: str = Depends(dependencies.token),
    service: EnrollmentClient = Depends(dependencies.enrollment),
):
    result = service.setup_totp(token)
    return TotpResponse(
        username=result.username,
        secret=result.secret,
        provisioning_uri=result.provisioning_uri,
        qr=result.qr,
    )


@router.post("/enrollment/confirm", response_model=UserResponse)
def confirm(
    data: ConfirmRequest,
    token: str = Depends(dependencies.token),
    service: EnrollmentClient = Depends(dependencies.enrollment),
):
    return service.confirm_totp(token, data.code)


@router.post("/credentials/renew", response_model=EnrollmentResponse)
def renew(
    request: Request,
    token: str = Depends(dependencies.token),
    service: EnrollmentClient = Depends(dependencies.enrollment),
):
    return present_enrollment(service.renew(token))
