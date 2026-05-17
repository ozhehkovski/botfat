from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from app.config import get_settings
from app.handlers.add_meal import router as add_meal_router
from app.handlers.common import router as common_router
from app.handlers.profile import router as profile_router
from app.handlers.settings import router as settings_router
from app.handlers.start import router as start_router
from app.handlers.summary import router as summary_router


def create_bot() -> Bot:
    settings = get_settings()
    return Bot(token=settings.telegram_bot_token)


def create_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.include_router(start_router)
    dp.include_router(add_meal_router)
    dp.include_router(summary_router)
    dp.include_router(profile_router)
    dp.include_router(settings_router)
    dp.include_router(common_router)
    return dp


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Запуск и настройка"),
            BotCommand(command="add", description="Добавить прием пищи"),
            BotCommand(command="done", description="Завершить добавление"),
            BotCommand(command="today", description="Сводка за сегодня"),
            BotCommand(command="yesterday", description="Сводка за вчера"),
            BotCommand(command="profile", description="Показать профиль"),
            BotCommand(command="settings", description="Настройки профиля"),
            BotCommand(command="delete_last", description="Удалить последнюю запись"),
            BotCommand(command="cancel", description="Отменить текущее действие"),
            BotCommand(command="help", description="Справка по командам"),
        ]
    )
