import logging
from datetime import datetime, timedelta

import database
import avito_api
from aiogram import Bot

logger = logging.getLogger(__name__)


def format_block(title: str, date_str: str, stats: dict) -> str:
    """Форматирует блок статистики для сообщения."""
    if not stats:
        return f"🗓 {title} ({date_str})\n❌ Данные не получены\n\n"

    v = stats.get('views', 0)
    c = stats.get('contacts', 0)
    s = float(stats.get('spend', 0.0) or 0.0)
    calls = stats.get('calls', 0)
    messages = stats.get('messages', 0)

    cpv = round(s / v, 2) if v > 0 else 0.0
    cpc = round(s / c, 2) if c > 0 else 0.0

    return (
        f"🗓 <b>{title} ({date_str})</b>\n"
        f"👁 Просмотры: {v}\n"
        f"📞 Контакты: {c}\n"
        f"     ┝ Звонки: {calls}\n"
        f"     ┕ Сообщения: {messages}\n"
        f"💰 Расходы: {round(s, 2)} ₽\n"
        f"📊 Цена/просмотр: {cpv} ₽\n"
        f"📊 Цена/контакт: {cpc} ₽\n\n"
    )


async def daily_report_job(bot: Bot):
    """Функция автоматической рассылки в 00:00."""
    logger.info("Запуск ежедневной рассылки отчетов...")

    stores = await database.get_all_stores()

    if not stores:
        return

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    for store in stores:
        try:
            data = await avito_api.get_full_report_data(
                store['client_id'],
                store['client_secret'],
                store['user_id'],
                today
            )

            if not data:
                logger.warning(
                    f"Не удалось получить данные для {store['store_name']}"
                )
                continue

            bal_text = "💳 Баланс: (нет доступа)"

            bal = await avito_api.get_balance(
                data['token'],
                store['user_id']
            )

            if bal:
                bal_text = (
                    f"💳 <b>Кошелёк:</b> {bal['wallet']} ₽ | "
                    f"<b>Аванс:</b> {bal['advance']} ₽"
                )

            msg = f"📈 <b>Статистика: {store['store_name'].upper()}</b>\n"
            msg += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"

            msg += format_block(
                "Сегодня",
                today.strftime("%d.%m"),
                data["today"]
            )

            msg += format_block(
                "Вчера",
                yesterday.strftime("%d.%m"),
                data["yesterday"]
            )

            msg += format_block(
                "Неделя",
                (
                    f"{(today - timedelta(days=7)).strftime('%d.%m')} – "
                    f"{today.strftime('%d.%m')}"
                ),
                data["week"]
            )

            msg += bal_text

            await bot.send_message(
                chat_id=store['chat_id'],
                text=msg,
                parse_mode="HTML"
            )

            logger.info(f"Отчет для {store['store_name']} отправлен.")

        except Exception as e:
            logger.error(f"Ошибка рассылки для {store['store_name']}: {e}")