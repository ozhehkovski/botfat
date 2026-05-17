from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message


router = Router()


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Команды:\n"
        "/start — запуск и настройка\n"
        "/add — добавить прием пищи\n"
        "/done — завершить добавление\n"
        "/today — сводка за сегодня\n"
        "/yesterday — сводка за вчера\n"
        "/profile — показать профиль\n"
        "/settings — изменить настройки\n"
        "/delete_last — удалить последнюю запись\n"
        "/cancel — отменить текущее действие"
    )


@router.message()
async def fallback_message(message: Message) -> None:
    await message.answer("Используй /add, чтобы добавить еду, или /help, чтобы посмотреть команды.")
