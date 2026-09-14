from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse, Response

from cofrap.application.results import Enrollment, UserInfo
from cofrap.contracts import ConfirmRequest, LoginRequest, RegisterRequest, TokenRequest
from cofrap.domain.errors import InvalidToken
from cofrap.frontend import dependencies
from cofrap.frontend.enrollment_routes import present_enrollment
from cofrap.frontend.openfaas_client import AuthenticationClient, EnrollmentClient
from cofrap.frontend.rendering import fragment, page

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
    result_view = present_enrollment(result)
    response = fragment(
        request, "enrollment", result=result_view, delivery_token=result.delivery_token
    )
    set_private_cookie(response, request, "enrollment", result.enrollment_token, 900)
    set_private_cookie(response, request, "delivery", result.delivery_token, 900)
    response.delete_cookie("cofrap_session")
    response.delete_cookie("cofrap_renewal")
    return response


def guest_page(request: Request, name: str, user: UserInfo | None):
    if user is not None:
        return RedirectResponse("/account", status_code=303)
    response = page(request, name)
    if request.cookies.get("cofrap_session"):
        response.delete_cookie("cofrap_session")
    return response


@router.get("/")
def home(request: Request, user: UserInfo | None = Depends(dependencies.browser_user)):
    return guest_page(request, "register", user)


@router.get("/login")
def login_page(request: Request, user: UserInfo | None = Depends(dependencies.browser_user)):
    return guest_page(request, "login", user)


@router.get("/delivery")
def delivery_page(request: Request):
    # Un GET ne consomme jamais la remise (préchargements, scanners de liens).
    return page(request, "delivery")


@router.get("/enrollment")
def resume_enrollment(
    request: Request,
    service: EnrollmentClient = Depends(dependencies.enrollment),
):
    token = request.cookies.get("cofrap_enrollment", "")
    user, redeemed = service.inspect(token)
    if redeemed:
        return page(request, "continue_enrollment", user=user)
    delivery_token = request.cookies.get("cofrap_delivery", "")
    delivery = service.delivery_view(delivery_token)
    return page(
        request,
        "enrollment",
        result={
            "user": user,
            **delivery,
        },
        delivery_token=delivery_token,
    )


@router.get("/account")
def account(
    request: Request,
    user: UserInfo | None = Depends(dependencies.browser_user),
):
    if user is None:
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie("cofrap_session")
        return response
    return page(request, "account", user=user, authenticated_user=user)


@router.post("/web/register")
def register(
    request: Request,
    data: Annotated[RegisterRequest, Form()],
    service: EnrollmentClient = Depends(dependencies.enrollment),
):
    return show_enrollment(request, service.register(data.username))


@router.post("/web/delivery")
def redeem(
    request: Request,
    data: Annotated[TokenRequest, Form()],
    service: EnrollmentClient = Depends(dependencies.enrollment),
):
    result = service.redeem_password(data.token)
    response = fragment(request, "password", result=result)
    response.delete_cookie("cofrap_delivery")
    return response


@router.post("/web/enrollment/totp")
def setup_totp(
    request: Request,
    service: EnrollmentClient = Depends(dependencies.enrollment),
):
    result = service.setup_totp(request.cookies.get("cofrap_enrollment", ""))
    return fragment(request, "totp", result=result, qr=result.qr)


@router.post("/web/enrollment/confirm")
def confirm_totp(
    request: Request,
    data: Annotated[ConfirmRequest, Form()],
    service: EnrollmentClient = Depends(dependencies.enrollment),
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
    service: AuthenticationClient = Depends(dependencies.authentication),
):
    result = service.authenticate(data.username, data.password.get_secret_value(), data.code)
    if result.status == "renewal_required":
        response = fragment(request, "expired", user=result.user)
        set_private_cookie(response, request, "renewal", result.token, 300)
        response.delete_cookie("cofrap_session")
    else:
        # HTMX doit naviguer vers une page GET stable, y compris au rechargement.
        if request.headers.get("HX-Request") == "true":
            response = Response(status_code=200, headers={"HX-Redirect": "/account"})
        else:
            response = RedirectResponse("/account", status_code=303)
        set_private_cookie(response, request, "session", result.token, 1800)
        response.delete_cookie("cofrap_renewal")
    return response


@router.post("/web/renew")
def renew(request: Request, service: EnrollmentClient = Depends(dependencies.enrollment)):
    return show_enrollment(request, service.renew(request.cookies.get("cofrap_renewal", "")))


@router.post("/web/logout")
def logout(request: Request, service: AuthenticationClient = Depends(dependencies.authentication)):
    try:
        service.logout(request.cookies.get("cofrap_session", ""))
    except InvalidToken:
        pass  # Une session déjà expirée peut toujours être effacée du navigateur.
    response = RedirectResponse("/login", status_code=303, headers={"HX-Redirect": "/login"})
    response.delete_cookie("cofrap_session")
    return response
