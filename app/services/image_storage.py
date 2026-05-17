from __future__ import annotations

from datetime import datetime
from pathlib import Path

from aiogram import Bot

from app.config import get_settings


class ImageStorageService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def save_telegram_photo(self, bot: Bot, telegram_id: int, file_id: str) -> str:
        telegram_file = await bot.get_file(file_id)
        file_path = telegram_file.file_path or f"{file_id}.jpg"
        suffix = Path(file_path).suffix or ".jpg"
        day_part = datetime.utcnow().strftime("%Y-%m-%d")
        base_dir = self.settings.absolute_photo_storage_dir / str(telegram_id) / day_part
        base_dir.mkdir(parents=True, exist_ok=True)
        local_path = base_dir / f"{file_id}{suffix}"
        await bot.download_file(file_path, destination=local_path)
        return str(local_path)
