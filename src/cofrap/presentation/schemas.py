from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, field_validator

Username = Annotated[str, StringConstraints(min_length=3, max_length=64, pattern=r"^[a-z0-9_.-]+$")]
Token = Annotated[str, StringConstraints(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]+$")]
TotpCode = Annotated[str, StringConstraints(pattern=r"^[0-9]{6}$")]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(InputModel):
    username: Username

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class TokenRequest(InputModel):
    token: Token


class ConfirmRequest(InputModel):
    code: TotpCode


class LoginRequest(RegisterRequest):
    password: SecretStr = Field(min_length=1, max_length=128)
    code: TotpCode


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    generated_at: datetime | None
    expires_at: datetime | None
    mfa_confirmed: bool
    expired: bool


class EnrollmentResponse(BaseModel):
    user: UserResponse
    enrollment_token: str
    delivery_url: str
    delivery_qr: str
    expires_at: datetime


class TotpResponse(BaseModel):
    username: str
    secret: str
    provisioning_uri: str
    qr: str


class PasswordResponse(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: Literal["authenticated", "renewal_required"]
    token: str
    expires_at: datetime
    user: UserResponse
