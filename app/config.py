from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    openai_api_key: str = Field(alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    database_url: str = Field(
        default="sqlite+aiosqlite:///data/calories_bot.sqlite3",
        alias="DATABASE_URL",
    )
    default_timezone: str = Field(default="Europe/Warsaw", alias="DEFAULT_TIMEZONE")
    summary_send_hour: int = Field(default=21, alias="SUMMARY_SEND_HOUR")
    max_photos_per_meal: int = Field(default=5, alias="MAX_PHOTOS_PER_MEAL")
    photo_storage_dir: str = Field(default="data/photos", alias="PHOTO_STORAGE_DIR")
    reminder_hours: str = Field(default="8,15,20", alias="REMINDER_HOURS")
    max_photo_size_bytes: int = 10 * 1024 * 1024
    openai_hourly_limit_per_user: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def absolute_photo_storage_dir(self) -> Path:
        return (BASE_DIR / self.photo_storage_dir).resolve()

    @property
    def parsed_reminder_hours(self) -> list[int]:
        hours: list[int] = []
        for value in self.reminder_hours.split(","):
            value = value.strip()
            if not value:
                continue
            hour = int(value)
            if 0 <= hour <= 23:
                hours.append(hour)
        return sorted(set(hours))


@lru_cache
def get_settings() -> Settings:
    return Settings()
