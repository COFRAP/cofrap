from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FrontendSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    public_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8000")
    cookie_secure: bool = False
    openfaas_gateway_url: AnyHttpUrl = AnyHttpUrl("http://127.0.0.1:8080")
    openfaas_timeout: float = Field(default=60, gt=0)
