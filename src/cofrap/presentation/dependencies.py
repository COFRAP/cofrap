from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cofrap.application.authentication import AuthenticationService
from cofrap.application.enrollment import EnrollmentService
from cofrap.domain.errors import InvalidToken

bearer = HTTPBearer(auto_error=False)


def token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> str:
    if credentials is None:
        raise InvalidToken()
    return credentials.credentials


def enrollment(request: Request) -> EnrollmentService:
    return request.app.state.enrollment


def authentication(request: Request) -> AuthenticationService:
    return request.app.state.authentication
