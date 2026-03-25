import re
from datetime import datetime, timedelta
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

import database
import config
import avito_api
from states import AddStore
from scheduler import format_block
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
        token = await avito_api.get_avito_token(store['client_id'], store['client_secret'])
        stores_with_status.append((store['id'], store['store_name'], bool(token)))
    return stores_with_status


@router.message(Command("get_id"))
async def cmd_get_id(message: types.Message):
    if message.chat.type == "private":
        return await message.answer("Эту команду нужно писать в группе, ID которой вы хотите узнать.")

    await message.answer(
        f"📍 <b>ID этого чата:</b> <code>{message.chat.id}</code>\n\n"
        f"Скопируйте это число (вместе с минусом) и отправьте его боту в личные сообщения при настройке магазина.",
        parse_mode="HTML"
    )


@router.message(Command("admin"))
@router.message(Command("start"))
async def cmd_admin(message: types.Message, state: FSMContext):
    await state.clear()

    if message.chat.type != "private":
        return await message.answer(
            "👋 Привет! Чтобы настроить отчеты Авито, напишите мне в личные сообщения.\n"
            "А в этой группе используйте команду /get_id, чтобы узнать её ID."
        )

    stores_status = await get_stores_with_status()
    await message.answer(
        f"👋 <b>Панель управления Авито</b>\n\n"
        f"Здесь вы можете добавлять магазины и привязывать их к чатам для ежедневных отчетов.\n\n"
        f"Всего магазинов в системе: {len(stores_status)}",
        reply_markup=get_admin_panel_keyboard(stores_status),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "refresh_panel")
@router.callback_query(F.data == "back_to_panel")
async def refresh_admin_panel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    stores_status = await get_stores_with_status()
    await callback.message.edit_text(
        f"👋 <b>Панель управления Авито</b>\n\nВсего магазинов в системе: {len(stores_status)}",
        reply_markup=get_admin_panel_keyboard(stores_status),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "add_store")
async def start_add_store(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AddStore.waiting_for_name)
    await callback.message.answer(
        "1️⃣ <b>Введите название магазина</b>\nЭто нужно только для вас (например: 'Кроссовки Омск')",
        reply_markup=get_chat_selection_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(AddStore.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена": return await cancel_handler(message, state)

    await state.update_data(name=message.text)
    await state.set_state(AddStore.waiting_for_chat_id)
    await message.answer(
        "2️⃣ <b>Введите ID чата для отчетов</b>\n\n"
        "• Напишите ID группы (например: <code>-100123456789</code>)\n"
        "• Или перешлите любое сообщение из группы\n"
        "• Или нажмите кнопку 'Выбрать чат' (если вы там есть)\n\n"
        "<i>ID группы можно узнать командой /get_id, написанной в самой группе.</i>",
        reply_markup=get_chat_selection_keyboard(),
        parse_mode="HTML"
    )

@router.message(AddStore.waiting_for_chat_id)
async def process_chat_id_universal(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена": return await cancel_handler(message, state)

    chat_id = None
    if message.chat_shared:
        chat_id = message.chat_shared.chat_id
    elif message.forward_from_chat:
        chat_id = message.forward_from_chat.id
    elif message.forward_origin and hasattr(message.forward_origin, 'chat'):
        chat_id = message.forward_origin.chat.id
    elif message.text and message.text.lstrip('-').isdigit():
        chat_id = int(message.text)

    if chat_id:
        await state.update_data(chat_id=chat_id)
        await state.set_state(AddStore.waiting_for_client_id)

        chat_name = f"ID: {chat_id}"
        try:
            c = await message.bot.get_chat(chat_id)
            chat_name = c.title
        except:
            pass

        await message.answer(
            f"✅ Чат привязан: <b>{chat_name}</b>\n\n"
            f"3️⃣ Теперь введите <b>Client ID</b> от Авито API:",
            reply_markup=get_chat_selection_keyboard(),
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Не удалось определить чат. Пришлите ID числом или перешлите сообщение.")

@router.message(AddStore.waiting_for_client_id)
async def process_client_id(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена": return await cancel_handler(message, state)
    await state.update_data(client_id=message.text.strip())
    await state.set_state(AddStore.waiting_for_client_secret)
    await message.answer("4️⃣ Введите <b>Client Secret</b> от Авито API:", parse_mode="HTML")


@router.message(AddStore.waiting_for_client_secret)
async def process_client_secret(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена": return await cancel_handler(message, state)

    user_data = await state.get_data()
    client_id = user_data['client_id']
    client_secret = message.text.strip()

    token = await avito_api.get_avito_token(client_id, client_secret)
    if not token:
        return await message.answer("❌ Ошибка: Неверный Client ID или Secret. Добавление отменено.")

    user_id = await avito_api.get_avito_user_id(token)
    if not user_id:
        return await message.answer("❌ Ошибка: Не удалось получить ID аккаунта от Авито.")

    await database.add_store(
        chat_id=user_data['chat_id'],
        store_name=user_data['name'],
        client_id=client_id,
        client_secret=client_secret,
        user_id=user_id
    )

    await message.answer(f"✅ Магазин добавлен!\nID аккаунта: <code>{user_id}</code>",
                         reply_markup=ReplyKeyboardRemove(), parse_mode="HTML")
    await state.clear()
    await cmd_admin(message, state)

@router.callback_query(StoreCallback.filter(F.action == "manage"))
async def manage_store(callback: types.CallbackQuery, callback_data: StoreCallback):
    store = await database.get_store_by_id(callback_data.store_id)
    if not store: return await callback.answer("Магазин не найден!")

    text = (
        f"🏪 <b>Магазин: {store['store_name']}</b>\n\n"
        f"📍 <b>Чат отчетов:</b> <code>{store['chat_id']}</code>\n"
        f"🔑 <b>Client ID:</b> <code>{store['client_id']}</code>\n"
        f"👤 <b>User ID:</b> <code>{store['user_id']}</code>\n\n"
        f"Отчеты приходят автоматически в 00:00."
    )
    await callback.message.edit_text(text, reply_markup=get_store_management_keyboard(store['id']), parse_mode="HTML")
    await callback.answer()


@router.callback_query(StoreCallback.filter(F.action == "test_send"))
async def manual_send_report(callback: types.CallbackQuery, callback_data: StoreCallback):
    await callback.answer("⏳ Запрашиваю данные из Авито...")
    store = await database.get_store_by_id(callback_data.store_id)

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=7)

    s_today = await avito_api.get_statistics(store['client_id'], store['client_secret'], store['user_id'], today, today)
    if not s_today: return await callback.message.answer("❌ Ошибка API Авито.")

    s_yesterday = await avito_api.get_statistics(store['client_id'], store['client_secret'], store['user_id'],
                                                 yesterday, yesterday)
    s_week = await avito_api.get_statistics(store['client_id'], store['client_secret'], store['user_id'], week_start,
                                            today)
    bal_text = ""
    bal = await avito_api.get_balance(s_today['token'])
    if bal:
        bal_text = f"💳 <b>Кошелёк:</b> {bal['wallet']} ₽ | <b>Аванс:</b> {bal['advance']} ₽"
    else:
        bal_text = "💳 <b>Баланс:</b> (нет доступа к кошельку)"

    msg = f"📈 <b>Статистика: {store['store_name'].upper()}</b>\n"
    msg += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
    msg += format_block("Сегодня", today.strftime("%d.%m"), s_today)
    msg += format_block("Вчера", yesterday.strftime("%d.%m"), s_yesterday)
    msg += format_block("Неделя", f"{week_start.strftime('%d.%m')} – {today.strftime('%d.%m')}", s_week)
    msg += bal_text

    try:
        await callback.bot.send_message(chat_id=store['chat_id'], text=msg, parse_mode="HTML")
        await callback.message.answer("✅ Отчет отправлен в чат клиента!")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка отправки в чат: {e}")


@router.callback_query(StoreCallback.filter(F.action == "delete"))
async def delete_store(callback: types.CallbackQuery, callback_data: StoreCallback):
    await database.delete_store(callback_data.store_id)
    await callback.answer("Магазин удален", show_alert=True)
    await refresh_admin_panel(callback, None)

@router.message(F.text == "❌ Отмена")
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    await cmd_admin(message, state)