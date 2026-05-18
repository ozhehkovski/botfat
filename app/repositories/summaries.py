from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailySummary, ReminderLog


class SummariesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_user_and_date(self, user_id: int, summary_date: date) -> DailySummary | None:
        result = await self.session.execute(
            select(DailySummary).where(
                DailySummary.user_id == user_id,
                DailySummary.summary_date == summary_date,
            )
        )
        return result.scalar_one_or_none()

    async def create_or_update(
        self,
        user_id: int,
        summary_date: date,
        payload: dict,
        summary_text: str,
        sent_at: datetime | None,
    ) -> DailySummary:
        summary = await self.get_by_user_and_date(user_id, summary_date)
        if summary is None:
            summary = DailySummary(user_id=user_id, summary_date=summary_date)
            self.session.add(summary)
        summary.total_calories = payload.get("total_calories")
        summary.total_protein = payload.get("total_protein")
        summary.total_fat = payload.get("total_fat")
        summary.total_carbs = payload.get("total_carbs")
        summary.total_fiber = payload.get("total_fiber")
        summary.calorie_limit = payload.get("calorie_limit")
        summary.protein_goal = payload.get("protein_goal")
        summary.summary_text = summary_text
        summary.sent_at = sent_at
        await self.session.flush()
        return summary

    async def get_reminder_log(self, user_id: int, reminder_date: date, reminder_hour: int) -> ReminderLog | None:
        result = await self.session.execute(
            select(ReminderLog).where(
                ReminderLog.user_id == user_id,
                ReminderLog.reminder_date == reminder_date,
                ReminderLog.reminder_hour == reminder_hour,
            )
        )
        return result.scalar_one_or_none()

    async def create_reminder_log(
        self,
        user_id: int,
        reminder_date: date,
        reminder_hour: int,
        sent_at: datetime,
    ) -> ReminderLog:
        reminder_log = ReminderLog(
            user_id=user_id,
            reminder_date=reminder_date,
            reminder_hour=reminder_hour,
            sent_at=sent_at,
        )
        self.session.add(reminder_log)
        await self.session.flush()
        return reminder_log
