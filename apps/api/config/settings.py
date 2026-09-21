from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    openrouter_api_key: SecretStr
    jev_model: str = Field(default="~typesafe/jev-latest", min_length=1)
    provider_timeout_seconds: float = Field(default=25, gt=0, le=120)

    @field_validator("openrouter_api_key")
    @classmethod
    def validate_api_key(cls, value: SecretStr) -> SecretStr:
        key = value.get_secret_value().strip()
        if not key:
            raise ValueError("OPENROUTER_API_KEY must not be empty")
        return SecretStr(key)
