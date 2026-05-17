from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def add_meal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Готово", callback_data="meal:done"),
                InlineKeyboardButton(text="Отмена", callback_data="meal:cancel"),
            ]
        ]
    )


def meal_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да, сохранить", callback_data="meal:confirm")],
            [InlineKeyboardButton(text="Изменить", callback_data="meal:revise")],
            [InlineKeyboardButton(text="Отмена", callback_data="meal:cancel")],
        ]
    )


def delete_confirmation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Удалить", callback_data="delete:confirm"),
                InlineKeyboardButton(text="Отмена", callback_data="delete:cancel"),
            ]
        ]
    )


def settings_keyboard(summary_enabled: bool, reminder_enabled: bool) -> InlineKeyboardMarkup:
    summary_label = "Выключить саммари" if summary_enabled else "Включить саммари"
    reminder_label = "Выключить напоминания" if reminder_enabled else "Включить напоминания"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Изменить вес", callback_data="settings:weight")],
            [InlineKeyboardButton(text="Изменить рост", callback_data="settings:height")],
            [InlineKeyboardButton(text="Изменить лимит калорий", callback_data="settings:calories")],
            [InlineKeyboardButton(text="Изменить цель по белку", callback_data="settings:protein")],
            [InlineKeyboardButton(text=summary_label, callback_data="settings:summary_toggle")],
            [InlineKeyboardButton(text=reminder_label, callback_data="settings:reminder_toggle")],
        ]
    )
