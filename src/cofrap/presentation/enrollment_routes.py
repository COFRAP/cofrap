from fastapi import APIRouter, Depends, Request

from cofrap.application.enrollment import EnrollmentService
from cofrap.application.results import Enrollment
from cofrap.presentation import dependencies
from cofrap.presentation.qr import qr_data_url
from cofrap.presentation.schemas import (
    ConfirmRequest,
    EnrollmentResponse,
    PasswordResponse,
    RegisterRequest,
    TokenRequest,
    TotpResponse,
    UserResponse,
)

router = APIRouter(prefix="/api", tags=["Inscription et renouvellement"])


def present_enrollment(result: Enrollment, base_url: str) -> EnrollmentResponse:
    # Le fragment ne part ni dans les journaux HTTP ni dans l’en-tête Referer.
    delivery_url = f"{base_url.rstrip('/')}/delivery#{result.delivery_token}"
    return EnrollmentResponse(
        user=UserResponse.model_validate(result.user),
        enrollment_token=result.enrollment_token,
        delivery_url=delivery_url,
        delivery_qr=qr_data_url(delivery_url),
        expires_at=result.expires_at,
    )


@router.post("/users", response_model=EnrollmentResponse, status_code=201)
def register(
    data: RegisterRequest,
    request: Request,
    service: EnrollmentService = Depends(dependencies.enrollment),
):
    return present_enrollment(
        service.register(data.username), str(request.app.state.settings.public_base_url)
    )


@router.post("/password-deliveries/redeem", response_model=PasswordResponse)
def redeem(data: TokenRequest, service: EnrollmentService = Depends(dependencies.enrollment)):
    return service.redeem_password(data.token)


@router.post("/enrollment/totp", response_model=TotpResponse)
def setup(
    token: str = Depends(dependencies.token),
    service: EnrollmentService = Depends(dependencies.enrollment),
):
    result = service.setup_totp(token)
    return TotpResponse(
        username=result.username,
        secret=result.secret,
        provisioning_uri=result.provisioning_uri,
        qr=qr_data_url(result.provisioning_uri),
    )


@router.post("/enrollment/confirm", response_model=UserResponse)
def confirm(
    data: ConfirmRequest,
    token: str = Depends(dependencies.token),
    service: EnrollmentService = Depends(dependencies.enrollment),
):
    return service.confirm_totp(token, data.code)


@router.post("/credentials/renew", response_model=EnrollmentResponse)
def renew(
    request: Request,
    token: str = Depends(dependencies.token),
    service: EnrollmentService = Depends(dependencies.enrollment),
):
    return present_enrollment(service.renew(token), str(request.app.state.settings.public_base_url))
