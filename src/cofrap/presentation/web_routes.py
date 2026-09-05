from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from cofrap.application.authentication import AuthenticationService
from cofrap.application.enrollment import EnrollmentService
from cofrap.application.results import Enrollment
from cofrap.presentation import dependencies
from cofrap.presentation.enrollment_routes import present_enrollment
from cofrap.presentation.qr import qr_data_url
from cofrap.presentation.rendering import fragment, page
from cofrap.presentation.schemas import ConfirmRequest, LoginRequest, RegisterRequest, TokenRequest

router = APIRouter(include_in_schema=False)


def set_private_cookie(response, request: Request, name: str, value: str, max_age: int):
    response.set_cookie(
        f"cofrap_{name}",
        value,
        max_age=max_age,
        httponly=True,
        secure=request.app.state.settings.cookie_secure,
        samesite="strict",
        path="/",
    )


def show_enrollment(request: Request, result: Enrollment):
    result_view = present_enrollment(result, str(request.app.state.settings.public_base_url))
    response = fragment(
        request, "enrollment", result=result_view, delivery_token=result.delivery_token
    )
    set_private_cookie(response, request, "enrollment", result.enrollment_token, 900)
    set_private_cookie(response, request, "delivery", result.delivery_token, 900)
    response.delete_cookie("cofrap_session")
    response.delete_cookie("cofrap_renewal")
    return response


@router.get("/")
def home(request: Request):
    return page(request, "register")


@router.get("/login")
def login_page(request: Request):
    return page(request, "login")


@router.get("/delivery")
def delivery_page(request: Request):
    # Un GET ne consomme jamais la remise (préchargements, scanners de liens).
    return page(request, "delivery")


@router.get("/enrollment")
def resume_enrollment(
    request: Request,
    service: EnrollmentService = Depends(dependencies.enrollment),
):
    token = request.cookies.get("cofrap_enrollment", "")
    user, redeemed = service.inspect(token)
    if redeemed:
        return page(request, "continue_enrollment", user=user)
    delivery_token = request.cookies.get("cofrap_delivery", "")
    url = f"{str(request.app.state.settings.public_base_url).rstrip('/')}/delivery#{delivery_token}"
    return page(
        request,
        "enrollment",
        result={
            "user": user,
            "delivery_url": url,
            "delivery_qr": qr_data_url(url),
        },
        delivery_token=delivery_token,
    )


@router.get("/account")
def account(
    request: Request,
    service: AuthenticationService = Depends(dependencies.authentication),
):
    user = service.current_user(request.cookies.get("cofrap_session", ""))
    return page(request, "account", user=user)


@router.post("/web/register")
def register(
    request: Request,
    data: Annotated[RegisterRequest, Form()],
    service: EnrollmentService = Depends(dependencies.enrollment),
):
    return show_enrollment(request, service.register(data.username))


@router.post("/web/delivery")
def redeem(
    request: Request,
    data: Annotated[TokenRequest, Form()],
    service: EnrollmentService = Depends(dependencies.enrollment),
):
    result = service.redeem_password(data.token)
    response = fragment(request, "password", result=result)
    response.delete_cookie("cofrap_delivery")
    return response


@router.post("/web/enrollment/totp")
def setup_totp(
    request: Request,
    service: EnrollmentService = Depends(dependencies.enrollment),
):
    result = service.setup_totp(request.cookies.get("cofrap_enrollment", ""))
    return fragment(request, "totp", result=result, qr=qr_data_url(result.provisioning_uri))


@router.post("/web/enrollment/confirm")
def confirm_totp(
    request: Request,
    data: Annotated[ConfirmRequest, Form()],
    service: EnrollmentService = Depends(dependencies.enrollment),
):
    user = service.confirm_totp(request.cookies.get("cofrap_enrollment", ""), data.code)
    response = fragment(request, "activated", user=user)
    response.delete_cookie("cofrap_enrollment")
    response.delete_cookie("cofrap_delivery")
    return response


@router.post("/web/login")
def login(
    request: Request,
    data: Annotated[LoginRequest, Form()],
    service: AuthenticationService = Depends(dependencies.authentication),
):
    result = service.authenticate(data.username, data.password.get_secret_value(), data.code)
    if result.status == "renewal_required":
        response = fragment(request, "expired", user=result.user)
        set_private_cookie(response, request, "renewal", result.token, 300)
        response.delete_cookie("cofrap_session")
    else:
        response = fragment(request, "account", user=result.user)
        set_private_cookie(response, request, "session", result.token, 1800)
        response.delete_cookie("cofrap_renewal")
    return response


@router.post("/web/renew")
def renew(request: Request, service: EnrollmentService = Depends(dependencies.enrollment)):
    return show_enrollment(request, service.renew(request.cookies.get("cofrap_renewal", "")))


@router.post("/web/logout")
def logout(request: Request, service: AuthenticationService = Depends(dependencies.authentication)):
    from cofrap.domain.errors import InvalidToken

    try:
        service.logout(request.cookies.get("cofrap_session", ""))
    except InvalidToken:
        pass  # Une session déjà expirée peut toujours être effacée du navigateur.
    response = RedirectResponse("/login", status_code=303, headers={"HX-Redirect": "/login"})
    response.delete_cookie("cofrap_session")
    return response
