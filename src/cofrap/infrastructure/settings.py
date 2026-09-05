from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import AnyHttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    postgres_user: str = "cofrap"
    postgres_password: SecretStr
    postgres_db: str = "cofrap"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 55432
    encryption_key: SecretStr
    public_base_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8000")
    cookie_secure: bool = False

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, value: SecretStr) -> SecretStr:
        try:
            Fernet(value.get_secret_value().encode())
        except (ValueError, TypeError) as exc:
            raise ValueError("Une clé Fernet valide est requise.") from exc
        return value

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
