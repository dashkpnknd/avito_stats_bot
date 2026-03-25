import logging
import database
import avito_api
from datetime import datetime, timedelta
from aiogram import Bot

logger = logging.getLogger(__name__)

def format_block(title: str, date_str: str, stats: dict) -> str:

    if not stats:
        return f"🗓 <b>{title} ({date_str})</b>\n❌ Данные не получены\n\n"

    return (
        f"🗓 <b>{title} ({date_str})</b>\n"
        f"👁 Просмотры: {stats['views']}\n"
        f"📞 Контакты: {stats['contacts']}\n"
        f"     ┝ Звонки: {stats['calls']}\n"
        f"     ┕ Сообщения: {stats['messages']}\n"
        f"💰 Расходы: {int(stats['spend'])} ₽\n"
        f"📊 Цена/просмотр: {stats['cpv']} ₽\n"
        f"📊 Цена/контакт: {stats['cpc']} ₽\n\n"
    )


async def daily_report_job(bot: Bot):
    logger.info("Запуск ежедневной рассылки отчетов...")

    stores = await database.get_all_stores()
    if not stores:
        logger.info("В базе нет магазинов для рассылки.")
        return
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=7)

    for store in stores:
        store_name = store['store_name']
        chat_id = store['chat_id']

        try:
            s_today = await avito_api.get_statistics(
                store['client_id'], store['client_secret'], store['user_id'], today, today
            )
            if not s_today:
                logger.warning(f"Не удалось получить данные для {store_name} (ошибка API)")
                continue

            s_yesterday = await avito_api.get_statistics(
                store['client_id'], store['client_secret'], store['user_id'], yesterday, yesterday
            )
            s_week = await avito_api.get_statistics(
                store['client_id'], store['client_secret'], store['user_id'], week_start, today
            )

            bal_text = ""
            if "token" in s_today:
                bal = await avito_api.get_balance(s_today['token'])
                if bal:
                    bal_text = f"💳 <b>Кошелёк:</b> {bal['wallet']} ₽ | <b>Аванс:</b> {bal['advance']} ₽"
                else:
                    bal_text = "💳 <b>Баланс:</b> (нет доступа к кошельку)"

            msg = f"📈 <b>Статистика: {store_name.upper()}</b>\n"
            msg += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
            msg += format_block("Сегодня", today.strftime("%d.%m"), s_today)
            msg += format_block("Вчера", yesterday.strftime("%d.%m"), s_yesterday)
            msg += format_block("Неделя", f"{week_start.strftime('%d.%m')} – {today.strftime('%d.%m')}", s_week)
            msg += bal_text

            await bot.send_message(chat_id=chat_id, text=msg, parse_mode="HTML")
            logger.info(f"Отчет для {store_name} успешно отправлен в чат {chat_id}")

        except Exception as e:
            logger.error(f"Критическая ошибка при отправке отчета для {store_name}: {e}")
            continue

    logger.info("Ежедневная рассылка завершена.")