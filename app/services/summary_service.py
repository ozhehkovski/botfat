from __future__ import annotations

from datetime import date, datetime

from app.repositories.meals import MealsRepository
from app.repositories.summaries import SummariesRepository
from app.utils.dates import day_bounds_utc, format_meal_time


class SummaryService:
    def __init__(self, meals_repo: MealsRepository, summaries_repo: SummariesRepository) -> None:
        self.meals_repo = meals_repo
        self.summaries_repo = summaries_repo

    async def build_day_summary(
        self,
        user,
        target_date: date,
        persist: bool = False,
        sent_at: datetime | None = None,
    ) -> tuple[str, dict]:
        start, end = day_bounds_utc(target_date, user.timezone)
        meals = await self.meals_repo.get_meals_between(user.id, start, end)

        if not meals:
            text = "Сегодня ты пока не добавлял еду." if sent_at else "За выбранный день нет добавленной еды."
            payload = {
                "total_calories": 0,
                "total_protein": 0,
                "total_fat": 0,
                "total_carbs": 0,
                "total_fiber": 0,
                "calorie_limit": user.daily_calorie_limit,
                "protein_goal": user.daily_protein_goal,
            }
            if persist:
                await self.summaries_repo.create_or_update(user.id, target_date, payload, text, sent_at)
            return text, payload

        total_calories = round(sum(meal.total_calories or 0 for meal in meals), 1)
        total_protein = round(sum(meal.total_protein or 0 for meal in meals), 1)
        total_fat = round(sum(meal.total_fat or 0 for meal in meals), 1)
        total_carbs = round(sum(meal.total_carbs or 0 for meal in meals), 1)
        total_fiber = round(sum(meal.total_fiber or 0 for meal in meals), 1)
        calorie_delta = (user.daily_calorie_limit or 0) - total_calories
        protein_delta = (user.daily_protein_goal or 0) - total_protein

        meal_lines = []
        for meal in meals:
            meal_lines.append(
                f"{format_meal_time(meal.created_at, user.timezone)} — {meal.meal_title or 'Прием пищи'}\n"
                f"{meal.total_calories or 0:.0f} ккал / Б: {meal.total_protein or 0:.0f} г / "
                f"Ж: {meal.total_fat or 0:.0f} г / У: {meal.total_carbs or 0:.0f} г / "
                f"Клетчатка: {meal.total_fiber or 0:.0f} г"
            )

        evaluation = self._build_evaluation(calorie_delta, protein_delta)
        text = (
            "Сводка за день:\n\n"
            f"Калории:\n{total_calories:.0f} / {user.daily_calorie_limit or 0} ккал\n"
            f"{'Осталось' if calorie_delta >= 0 else 'Превышение'}: {abs(calorie_delta):.0f} ккал\n\n"
            f"Белок:\n{total_protein:.0f} / {user.daily_protein_goal or 0} г\n"
            f"{'Осталось' if protein_delta >= 0 else 'Сверх цели'}: {abs(protein_delta):.0f} г\n\n"
            f"Жиры: {total_fat:.0f} г\n"
            f"Углеводы: {total_carbs:.0f} г\n"
            f"Клетчатка: {total_fiber:.0f} г\n\n"
            "Приемы пищи:\n"
            + "\n\n".join(meal_lines)
            + f"\n\nОценка дня:\n{evaluation}"
        )
        payload = {
            "total_calories": total_calories,
            "total_protein": total_protein,
            "total_fat": total_fat,
            "total_carbs": total_carbs,
            "total_fiber": total_fiber,
            "calorie_limit": user.daily_calorie_limit,
            "protein_goal": user.daily_protein_goal,
        }
        if persist:
            await self.summaries_repo.create_or_update(user.id, target_date, payload, text, sent_at)
        return text, payload

    @staticmethod
    def _build_evaluation(calorie_delta: float, protein_delta: float) -> str:
        if calorie_delta >= 0 and protein_delta <= 0:
            return "День выглядит сбалансированно: по калориям ты в пределах лимита, цель по белку закрыта."
        if calorie_delta < 0:
            return "Сегодня есть превышение по калориям. Завтра можно сделать приемы пищи чуть легче."
        if protein_delta > 0:
            return "По калориям все неплохо, но белка пока не хватило до цели."
        return "День получился средним по балансу. Можно ориентироваться на белок и размер порций."
