import re
from datetime import datetime, timedelta

from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

import database
import avito_api
from states import AddStore
from keyboards import (
    get_admin_panel_keyboard,
    get_store_management_keyboard,
    get_chat_selection_keyboard,
    StoreCallback
)

router = Router()


async def get_stores_with_status() -> list:
    stores = await database.get_all_stores()
    stores_with_status = []

    for store in stores:
        token = await avito_api.get_avito_token(
            store['client_id'],
            store['client_secret']
        )

        stores_with_status.append(
            (store['id'], store['store_name'], bool(token))
        )

    return stores_with_status


@router.message(Command("get_id"))
async def cmd_get_id(message: types.Message):
    if message.chat.type == "private":
        return await message.answer("Эту команду нужно писать в группе.")

    await message.answer(
        f"📍 ID чата: {message.chat.id}",
        parse_mode="HTML"
    )


@router.message(Command("admin"))
@router.message(Command("start"))
async def cmd_admin(message: types.Message, state: FSMContext):
    await state.clear()

    if message.chat.type != "private":
        return

    stores_status = await get_stores_with_status()

    await message.answer(
        f"👋 Панель управления\n\nВсего магазинов: {len(stores_status)}",
        reply_markup=get_admin_panel_keyboard(stores_status),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "refresh_panel")
async def refresh_admin_panel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()

    stores_status = await get_stores_with_status()

    await callback.message.edit_text(
        f"👋 Панель управления\n\nВсего магазинов: {len(stores_status)}",
        reply_markup=get_admin_panel_keyboard(stores_status),
        parse_mode="HTML"
    )

    await callback.answer()


@router.callback_query(F.data == "add_store")
async def start_add_store(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddStore.waiting_for_name)

    await callback.message.answer(
        "1️⃣ Введите название магазина:",
        reply_markup=get_chat_selection_keyboard()
    )


@router.message(AddStore.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddStore.waiting_for_chat_id)

    await message.answer("2️⃣ Введите ID чата:")


@router.message(AddStore.waiting_for_chat_id)
async def process_chat_id(message: types.Message, state: FSMContext):
    chat_id = None

    if message.chat_shared:
        chat_id = message.chat_shared.chat_id

    elif message.forward_from_chat:
        chat_id = message.forward_from_chat.id

    elif message.text:
        raw_text = message.text.lstrip('-')

        if raw_text.isdigit():
            chat_id = int(message.text)

    if chat_id is not None:
        await state.update_data(chat_id=chat_id)
        await state.set_state(AddStore.waiting_for_client_id)

        return await message.answer(
            "3️⃣ Введите Client ID:",
            reply_markup=ReplyKeyboardRemove()
        )

    await message.answer(
        "❌ Не удалось получить ID чата.\n\n"
        "Используйте кнопку выбора чата, перешлите сообщение из нужной "
        "группы или введите ID вручную."
    )


@router.message(AddStore.waiting_for_client_id)
async def process_client_id(message: types.Message, state: FSMContext):
    await state.update_data(client_id=message.text.strip())
    await state.set_state(AddStore.waiting_for_client_secret)

    await message.answer("4️⃣ Введите Client Secret:")


@router.message(AddStore.waiting_for_client_secret)
async def process_client_secret(message: types.Message, state: FSMContext):
    user_data = await state.get_data()

    client_id = user_data['client_id']
    client_secret = message.text.strip()

    token = await avito_api.get_avito_token(
        client_id,
        client_secret
    )

    if not token:
        return await message.answer("❌ Ошибка ключей.")

    user_id = await avito_api.get_avito_user_id(token)

    await database.add_store(
        user_data['chat_id'],
        user_data['name'],
        client_id,
        client_secret,
        user_id
    )

    await message.answer("✅ Магазин добавлен!")
    await state.clear()


@router.callback_query(StoreCallback.filter(F.action == "manage"))
async def manage_store(
    callback: types.CallbackQuery,
    callback_data: StoreCallback
):
    store = await database.get_store_by_id(callback_data.store_id)

    text = (
        f"🏪 {store['store_name']}\n"
        f"📍 ID: {store['chat_id']}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_store_management_keyboard(store['id']),
        parse_mode="HTML"
    )


@router.callback_query(StoreCallback.filter(F.action == "test_send"))
async def manual_send_report(
    callback: types.CallbackQuery,
    callback_data: StoreCallback
):
    await callback.answer("⏳ Собираю данные...")

    store = await database.get_store_by_id(callback_data.store_id)

    res = await avito_api.get_full_report_data(
        store['client_id'],
        store['client_secret'],
        store['user_id']
    )

    if not res:
        return await callback.message.answer("❌ Не удалось получить данные.")

    bal = await avito_api.get_balance(
        res['token'],
        store['user_id']
    )

    stats = res["stats"]

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=7)

    msg = (
        f"📈 <b>Статистика: {store['store_name'].upper()}</b>\n"
        f"⎯⎯⎯⎯⎯⎯⎯⎯⎯"
        f"⎯⎯⎯⎯⎯⎯⎯"
        f"⎯⎯⎯⎯⎯\n\n"
    )

    for key, name, date_text in [
        ("today", "Сегодня", today.strftime("%d.%m")),
        ("yesterday", "Вчера", yesterday.strftime("%d.%m")),
        (
            "week",
            "Неделя",
            f"{week_start.strftime('%d.%m')} - {today.strftime('%d.%m')}"
        )
    ]:
        s = stats.get(key, {})

        views = s.get("views", 0)
        contacts = s.get("contacts", 0)
        spend = s.get("spend", 0.0)

        cpv = round(spend / views, 2) if views > 0 else 0.0
        cpc = round(spend / contacts, 2) if contacts > 0 else 0.0

        msg += (
            f"🗓 <b>{name} ({date_text})</b>\n"
            f"👁 Просмотры: {views}\n"
            f"📞 Контакты: {contacts}\n"
            f"💰 Расходы: {round(spend, 2)} ₽\n"
            f"📊 Цена/просмотр: {cpv} ₽\n"
            f"📊 Цена/контакт: {cpc} ₽\n\n"
        )

    msg += (
        f"💳 <b>Кошелек:</b> {bal['wallet']} ₽ | "
        f"<b>Аванс:</b> {bal['advance']} ₽"
    )

    await callback.bot.send_message(
        chat_id=store['chat_id'],
        text=msg,
        parse_mode="HTML"
    )


@router.callback_query(StoreCallback.filter(F.action == "delete"))
async def delete_store(
    callback: types.CallbackQuery,
    callback_data: StoreCallback
):
    await database.delete_store(callback_data.store_id)

    await callback.answer(
        "Удалено",
        show_alert=True
    )

    await refresh_admin_panel(callback, None)