from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import get_settings
from app.database import SessionLocal
from app.repositories.meals import MealsRepository
from app.repositories.summaries import SummariesRepository
from app.repositories.users import UsersRepository
from app.services.summary_service import SummaryService
from app.utils.dates import local_date, now_in_timezone


logger = logging.getLogger(__name__)


class SummaryScheduler:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.settings = get_settings()

    def start(self) -> None:
        self.scheduler.add_job(self._run_scheduled_jobs, "interval", minutes=1)
        self.scheduler.start()

    async def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    async def _run_scheduled_jobs(self) -> None:
        async with SessionLocal() as session:
            users_repo = UsersRepository(session)
            meals_repo = MealsRepository(session)
            summaries_repo = SummariesRepository(session)
            summary_service = SummaryService(meals_repo, summaries_repo)
            reminder_hours = set(self.settings.parsed_reminder_hours)
            summary_users = await users_repo.list_summary_enabled_users()
            reminder_users = await users_repo.list_reminder_enabled_users()

            for user in summary_users:
                current_local = now_in_timezone(user.timezone)
                if current_local.hour != user.summary_hour or current_local.minute != 0:
                    continue

                today = local_date(user.timezone)
                existing = await summaries_repo.get_by_user_and_date(user.id, today)
                if existing and existing.sent_at is not None:
                    continue

                try:
                    summary_text, payload = await summary_service.build_day_summary(
                        user=user,
                        target_date=today,
                        persist=True,
                        sent_at=datetime.utcnow(),
                    )
                    await self.bot.send_message(user.telegram_id, summary_text)
                    await summaries_repo.create_or_update(
                        user.id,
                        today,
                        payload,
                        summary_text,
                        datetime.utcnow(),
                    )
                    await session.commit()
                except Exception:
                    logger.exception("Failed to send daily summary to user %s", user.telegram_id)
                    await session.rollback()

            for user in reminder_users:
                current_local = now_in_timezone(user.timezone)
                if current_local.minute != 0 or current_local.hour not in reminder_hours:
                    continue

                today = local_date(user.timezone)
                existing = await summaries_repo.get_reminder_log(user.id, today, current_local.hour)
                if existing is not None:
                    continue

                try:
                    await self.bot.send_message(
                        user.telegram_id,
                        self._build_reminder_text(current_local.hour),
                    )
                    await summaries_repo.create_reminder_log(
                        user_id=user.id,
                        reminder_date=today,
                        reminder_hour=current_local.hour,
                        sent_at=datetime.utcnow(),
                    )
                    await session.commit()
                except Exception:
                    logger.exception(
                        "Failed to send reminder to user %s for hour %s",
                        user.telegram_id,
                        current_local.hour,
                    )
                    await session.rollback()

    @staticmethod
    def _build_reminder_text(hour: int) -> str:
        if hour == 8:
            return "Доброе утро! Не забудь добавить завтрак или напитки, когда поешь."
        if hour == 15:
            return "Напоминание: если уже был обед или перекус, добавь его в дневник питания."
        if hour == 20:
            return "Вечернее напоминание: добавь ужин и все, что ел или пил сегодня."
        return "Напоминание: не забудь добавить прием пищи в дневник."
