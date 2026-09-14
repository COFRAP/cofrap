from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cofrap.application.results import UserInfo
from cofrap.domain.errors import CredentialsExpired, InvalidToken
from cofrap.frontend.openfaas_client import AuthenticationClient, EnrollmentClient

bearer = HTTPBearer(auto_error=False)


def token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    if credentials is None:
        raise InvalidToken()
    return credentials.credentials


def enrollment(request: Request) -> EnrollmentClient:
    return request.app.state.enrollment


def authentication(request: Request) -> AuthenticationClient:
    return request.app.state.authentication


def browser_user(
    request: Request, service: AuthenticationClient = Depends(authentication)
) -> UserInfo | None:
    session_token = request.cookies.get("cofrap_session")
    if not session_token:
        return None
    try:
        return service.current_user(session_token)
    except (InvalidToken, CredentialsExpired):
        return None
