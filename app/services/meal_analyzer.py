from __future__ import annotations

import logging

from app.config import get_settings
from app.repositories.meals import MealsRepository
from app.services.openai_service import OpenAIService


logger = logging.getLogger(__name__)


class RateLimitExceededError(Exception):
    pass


class MealAnalyzerService:
    def __init__(self, meals_repo: MealsRepository, openai_service: OpenAIService) -> None:
        self.meals_repo = meals_repo
        self.openai_service = openai_service
        self.settings = get_settings()

    async def analyze_meal(
        self,
        user_id: int,
        text: str | None,
        image_paths: list[str],
        profile_context: dict,
        clarification: str | None = None,
    ) -> dict:
        recent_count = await self.meals_repo.count_recent_openai_logs(user_id)
        if recent_count >= self.settings.openai_hourly_limit_per_user:
            raise RateLimitExceededError

        try:
            result, meta = await self.openai_service.analyze_meal(
                text=text,
                image_paths=image_paths,
                profile_context=profile_context,
                clarification=clarification,
            )
            await self.meals_repo.create_openai_log(
                user_id=user_id,
                meal_entry_id=None,
                request_payload=meta["request_payload"],
                response_payload=meta["response_payload"],
                model=meta["model"],
                input_tokens=meta["input_tokens"],
                output_tokens=meta["output_tokens"],
                cost=None,
            )
            return result
        except Exception as exc:
            logger.exception("Meal analyze failed")
            await self.meals_repo.create_openai_log(
                user_id=user_id,
                meal_entry_id=None,
                request_payload=None,
                response_payload=None,
                model=self.openai_service.model,
                input_tokens=None,
                output_tokens=None,
                cost=None,
                error=str(exc),
            )
            raise

    async def revise_meal(self, user_id: int, current_json: dict, user_edit: str) -> dict:
        recent_count = await self.meals_repo.count_recent_openai_logs(user_id)
        if recent_count >= self.settings.openai_hourly_limit_per_user:
            raise RateLimitExceededError

        try:
            result, meta = await self.openai_service.revise_meal(current_json, user_edit)
            await self.meals_repo.create_openai_log(
                user_id=user_id,
                meal_entry_id=None,
                request_payload=meta["request_payload"],
                response_payload=meta["response_payload"],
                model=meta["model"],
                input_tokens=meta["input_tokens"],
                output_tokens=meta["output_tokens"],
                cost=None,
            )
            return result
        except Exception as exc:
            logger.exception("Meal revise failed")
            await self.meals_repo.create_openai_log(
                user_id=user_id,
                meal_entry_id=None,
                request_payload=None,
                response_payload=None,
                model=self.openai_service.model,
                input_tokens=None,
                output_tokens=None,
                cost=None,
                error=str(exc),
            )
            raise
