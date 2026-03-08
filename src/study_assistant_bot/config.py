from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from study_assistant_bot.enums import UserRole

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "telegram-study-assistant"
    bot_token: str = ""
    database_url: str = "sqlite+aiosqlite:///./data/study_assistant.db"
    log_level: str = "INFO"
    admin_telegram_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)
    student_telegram_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)

    @field_validator("admin_telegram_ids", "student_telegram_ids", mode="before")
    @classmethod
    def parse_telegram_ids(cls, value: Any) -> list[int]:
        if value in (None, "", []):
            return []

        if isinstance(value, int):
            return [value]

        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]

        return [int(item) for item in value]

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value

        if value.startswith("sqlite:///") and not value.startswith("sqlite+aiosqlite:///"):
            return value.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

        return value

    @property
    def allowed_telegram_ids(self) -> set[int]:
        return set(self.admin_telegram_ids) | set(self.student_telegram_ids)

    def role_for_user(self, telegram_id: int) -> UserRole | None:
        if telegram_id in self.admin_telegram_ids:
            return UserRole.ADMIN

        if telegram_id in self.student_telegram_ids:
            return UserRole.STUDENT

        return None

    def validate_runtime(self) -> None:
        if not self.bot_token:
            raise ValueError("BOT_TOKEN is not configured.")

        if not self.allowed_telegram_ids:
            raise ValueError(
                "Configure at least one Telegram user ID in ADMIN_TELEGRAM_IDS or "
                "STUDENT_TELEGRAM_IDS."
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
