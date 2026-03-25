import asyncio
import logging
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import database
from handlers import router
from scheduler import daily_report_job


async def main():
    await database.init_db()
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(router)

    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    scheduler.add_job(
        daily_report_job,
        trigger='cron',
        hour=0,
        minute=0,
        kwargs={'bot': bot}
    )
    scheduler.start()

    logging.info("Бот запущен. Планировщик работает.")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

async def get_store_by_id(store_id: int):
    async with aiosqlite.connect(config.DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM stores WHERE id = ?', (store_id,)) as cursor:
            return await cursor.fetchone()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")