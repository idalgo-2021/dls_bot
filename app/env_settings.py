import logging
from pathlib import Path

from pydantic import (
    SecretStr,
    AnyHttpUrl,
    field_validator,
    model_validator,
)

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    TELEGRAM_BOT_TOKEN: SecretStr
    BOT_RUN_MODE: str = "polling"

    # Webhook settings
    WEBHOOK_URL: Optional[AnyHttpUrl] = None
    WEBHOOK_PORT: Optional[int] = 8443
    WEBHOOK_SECRET: Optional[SecretStr] = None
    WEBHOOK_PATH: Optional[str] = None
    WEBHOOK_CERT_PATH: Optional[str] = None

    @field_validator("BOT_RUN_MODE")
    @classmethod
    def validate_bot_run_mode(cls, v: str) -> str:
        mode = v.lower()
        if mode not in ["polling", "webhook"]:
            raise ValueError("BOT_RUN_MODE must be 'polling' or 'webhook'")
        return mode

    @model_validator(mode="after")
    def check_webhook_settings_are_present(self) -> "Settings":
        if self.BOT_RUN_MODE == "webhook":
            if not self.WEBHOOK_URL:
                raise ValueError("WEBHOOK_URL is required for webhook mode")
            if not self.WEBHOOK_PORT:
                raise ValueError("WEBHOOK_PORT is required for webhook mode")
            if not self.WEBHOOK_SECRET:
                raise ValueError("WEBHOOK_SECRET is required for webhook mode")
        return self

    @model_validator(mode="after")
    def process_webhook_path(self) -> "Settings":
        if self.BOT_RUN_MODE == "webhook":
            if self.WEBHOOK_PATH is None:
                logger.info(
                    "WEBHOOK_PATH not set, defaulting to" " '/' for webhook mode."
                )
                self.WEBHOOK_PATH = "/"
            elif not self.WEBHOOK_PATH.startswith("/"):
                raise ValueError("WEBHOOK_PATH must start with a '/' if provided.")
        return self

    @model_validator(mode="after")
    def validate_webhook_cert_path(self) -> "Settings":
        if self.BOT_RUN_MODE == "webhook" and self.WEBHOOK_CERT_PATH:
            path = Path(self.WEBHOOK_CERT_PATH)
            if not path.is_file():
                raise ValueError(
                    f"WEBHOOK_CERT_PATH '{self.WEBHOOK_CERT_PATH}' does not point to a valid file."
                )
        return self
