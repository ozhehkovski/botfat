from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.database import SessionLocal
from app.repositories.meals import MealsRepository
from app.repositories.summaries import SummariesRepository
from app.repositories.users import UsersRepository
from app.services.summary_service import SummaryService
from app.utils.dates import local_date


router = Router()


async def _send_summary(message: Message, days_offset: int) -> None:
    async with SessionLocal() as session:
        users_repo = UsersRepository(session)
        user = await users_repo.get_by_telegram_id(message.from_user.id)
        if user is None or not user.onboarding_completed:
            await message.answer("Сначала нужно настроить профиль. Укажи свой вес в кг.")
            return

        meals_repo = MealsRepository(session)
        summaries_repo = SummariesRepository(session)
        service = SummaryService(meals_repo, summaries_repo)
        target_date = local_date(user.timezone, days_offset)
        text, _ = await service.build_day_summary(user=user, target_date=target_date, persist=False)
        if not _has_meals_text(text):
            await message.answer(
                "Сегодня пока нет добавленной еды." if days_offset == 0 else "За вчера нет добавленной еды."
            )
            return
        title = "Сводка за сегодня:\n\n" if days_offset == 0 else "Сводка за вчера:\n\n"
        await message.answer(title + text.replace("Сводка за день:\n\n", "", 1))


def _has_meals_text(text: str) -> bool:
    return "Приемы пищи:" in text


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    await _send_summary(message, 0)


@router.message(Command("yesterday"))
async def cmd_yesterday(message: Message) -> None:
    await _send_summary(message, -1)
