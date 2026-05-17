from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import MealEntry, MealItem, MealPhoto, OpenAILog, UserState


class MealsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_state(self, telegram_id: int, state: str | None, data: dict | None) -> None:
        entity = await self.session.get(UserState, telegram_id)
        payload = json.dumps(data or {}, ensure_ascii=False)
        if entity is None:
            entity = UserState(telegram_id=telegram_id, state=state, data_json=payload)
            self.session.add(entity)
        else:
            entity.state = state
            entity.data_json = payload
        await self.session.flush()

    async def get_state(self, telegram_id: int) -> tuple[str | None, dict]:
        entity = await self.session.get(UserState, telegram_id)
        if entity is None:
            return None, {}
        return entity.state, json.loads(entity.data_json or "{}")

    async def clear_state(self, telegram_id: int) -> None:
        await self.session.execute(delete(UserState).where(UserState.telegram_id == telegram_id))
        await self.session.flush()

    async def create_confirmed_meal(
        self,
        user_id: int,
        source_type: str,
        original_text: str | None,
        analysis: dict,
        photos: list[dict],
    ) -> MealEntry:
        meal = MealEntry(
            user_id=user_id,
            meal_title=analysis.get("meal_title"),
            source_type=source_type,
            original_text=original_text,
            total_calories=analysis["total"]["calories"],
            total_protein=analysis["total"]["protein"],
            total_fat=analysis["total"]["fat"],
            total_carbs=analysis["total"]["carbs"],
            confidence=analysis.get("confidence"),
            status="confirmed",
            openai_raw_response=json.dumps(analysis, ensure_ascii=False),
            notes=analysis.get("notes"),
        )
        self.session.add(meal)
        await self.session.flush()

        for item in analysis.get("items", []):
            self.session.add(
                MealItem(
                    meal_entry_id=meal.id,
                    name=item["name"],
                    quantity=item.get("quantity"),
                    unit=item.get("unit"),
                    calories=item.get("calories"),
                    protein=item.get("protein"),
                    fat=item.get("fat"),
                    carbs=item.get("carbs"),
                    notes=item.get("notes"),
                )
            )

        for photo in photos:
            self.session.add(
                MealPhoto(
                    meal_entry_id=meal.id,
                    telegram_file_id=photo.get("telegram_file_id"),
                    local_path=photo.get("local_path"),
                )
            )
        await self.session.flush()
        return meal

    async def get_last_confirmed_meal(self, user_id: int) -> MealEntry | None:
        result = await self.session.execute(
            select(MealEntry)
            .where(MealEntry.user_id == user_id, MealEntry.status == "confirmed")
            .options(selectinload(MealEntry.items))
            .order_by(desc(MealEntry.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def soft_delete_meal(self, meal: MealEntry) -> None:
        meal.status = "deleted"
        await self.session.flush()

    async def get_meals_between(self, user_id: int, start: datetime, end: datetime) -> list[MealEntry]:
        result = await self.session.execute(
            select(MealEntry)
            .where(
                MealEntry.user_id == user_id,
                MealEntry.status == "confirmed",
                MealEntry.created_at >= start,
                MealEntry.created_at < end,
            )
            .options(selectinload(MealEntry.items))
            .order_by(MealEntry.created_at.asc())
        )
        return list(result.scalars().all())

    async def create_openai_log(
        self,
        user_id: int | None,
        meal_entry_id: int | None,
        request_payload: str | None,
        response_payload: str | None,
        model: str,
        input_tokens: int | None,
        output_tokens: int | None,
        cost: float | None,
        error: str | None = None,
    ) -> None:
        self.session.add(
            OpenAILog(
                user_id=user_id,
                meal_entry_id=meal_entry_id,
                request_payload=request_payload,
                response_payload=response_payload,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost,
                error=error,
            )
        )
        await self.session.flush()

    async def count_recent_openai_logs(self, user_id: int, minutes: int = 60) -> int:
        since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        result = await self.session.execute(
            select(func.count(OpenAILog.id)).where(
                OpenAILog.user_id == user_id,
                OpenAILog.created_at >= since,
                OpenAILog.error.is_(None),
            )
        )
        return int(result.scalar_one() or 0)
