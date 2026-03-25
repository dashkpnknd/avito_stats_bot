from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestChat
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData

class StoreCallback(CallbackData, prefix="store"):
    action: str  # 'manage', 'delete'
    store_id: int

def get_admin_panel_keyboard(stores_with_status: list) -> InlineKeyboardMarkup:

    builder = InlineKeyboardBuilder()

    for store_id, store_name, is_active in stores_with_status:
        status_icon = "🟢" if is_active else "🔴"
        builder.button(
            text=f"{status_icon} {store_name}",
            callback_data=StoreCallback(action="manage", store_id=store_id)
        )

    builder.row(InlineKeyboardButton(text="➕ Добавить магазин", callback_data="add_store"))
    builder.row(InlineKeyboardButton(text="🔄 Обновить список", callback_data="refresh_panel"))

    builder.adjust(1)
    return builder.as_markup()


def get_store_management_keyboard(store_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(
        text="🚀 Отправить отчет сейчас",
        callback_data=StoreCallback(action="test_send", store_id=store_id)
    )
    builder.button(
        text="🗑️ Удалить магазин",
        callback_data=StoreCallback(action="delete", store_id=store_id)
    )
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_panel")

    builder.adjust(1)
    return builder.as_markup()


def get_chat_selection_keyboard() -> ReplyKeyboardMarkup:
    request_button = KeyboardButton(
        text="📍 Выбрать чат из списка",
        request_chat=KeyboardButtonRequestChat(
            request_id=1,
            chat_is_channel=False,
            bot_is_member=True
        )
    )

    cancel_button = KeyboardButton(text="❌ Отмена")

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [request_button],
            [cancel_button]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    return keyboard