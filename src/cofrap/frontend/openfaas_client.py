"""Typed HTTP adapters. Mutations are never automatically retried."""

import httpx
from pydantic import TypeAdapter, ValidationError

from cofrap.application.results import (
    Authentication,
    Enrollment,
    PasswordDelivery,
    TotpSetup,
    UserInfo,
)
from cofrap.contracts import Token
from cofrap.domain.errors import BackendUnavailable, InvalidToken
from cofrap.http_errors import ERROR_TYPES

FUNCTIONS = ("generate-password", "generate-2fa", "authenticate")


class OpenFaaSClient:
    def __init__(self, http: httpx.Client):
        self.http = http

    def call(self, function, operation, payload, result_type=None):
        if "token" in payload:
            try:
                TypeAdapter(Token).validate_python(payload["token"])
            except ValidationError as exc:
                raise InvalidToken() from exc
        try:
            response = self.http.post(f"/function/{function}/{operation}", json=payload)
            if response.is_error:
                try:
                    error_type = ERROR_TYPES.get(response.json()["error"]["code"])
                except (ValueError, KeyError, TypeError):
                    error_type = None
                if error_type:
                    raise error_type()
                raise BackendUnavailable()
            if response.status_code == 204:
                return None
            if not response.is_success:
                raise BackendUnavailable()
            data = response.json()
            return TypeAdapter(result_type).validate_python(data) if result_type else data
        except (httpx.HTTPError, ValueError, ValidationError) as exc:
            raise BackendUnavailable() from exc

    def ready(self):
        try:
            for function in FUNCTIONS:
                response = self.http.get(f"/function/{function}/health/ready")
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise BackendUnavailable() from exc


class EnrollmentClient:
    def __init__(self, gateway: OpenFaaSClient):
        self.gateway = gateway

    def register(self, username):
        return self.gateway.call(
            "generate-password", "register", {"username": username}, Enrollment
        )

    def renew(self, token):
        return self.gateway.call("generate-password", "renew", {"token": token}, Enrollment)

    def redeem_password(self, token):
        return self.gateway.call("generate-password", "redeem", {"token": token}, PasswordDelivery)

    def inspect(self, token):
        result = self.gateway.call("generate-password", "inspect", {"token": token})
        return TypeAdapter(UserInfo).validate_python(result["user"]), result["redeemed"]

    def delivery_view(self, token):
        return self.gateway.call("generate-password", "qr", {"token": token})

    def setup_totp(self, token):
        return self.gateway.call("generate-2fa", "setup", {"token": token}, TotpSetup)

    def confirm_totp(self, token, code):
        return self.gateway.call(
            "generate-2fa", "confirm", {"token": token, "code": code}, UserInfo
        )


class AuthenticationClient:
    def __init__(self, gateway: OpenFaaSClient):
        self.gateway = gateway

    def authenticate(self, username, password, code):
        return self.gateway.call(
            "authenticate",
            "login",
            {"username": username, "password": password, "code": code},
            Authentication,
        )

    def current_user(self, token):
        return self.gateway.call("authenticate", "me", {"token": token}, UserInfo)

    def logout(self, token):
        return self.gateway.call("authenticate", "logout", {"token": token})
