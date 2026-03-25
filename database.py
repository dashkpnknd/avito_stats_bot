import aiosqlite
import config

async def init_db():
    async with aiosqlite.connect(config.DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS stores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                store_name TEXT NOT NULL,
                client_id TEXT NOT NULL,
                client_secret TEXT NOT NULL,
                user_id INTEGER -- Добавили новую колонку!
            )
        ''')
        await db.commit()

async def add_store(chat_id: int, store_name: str, client_id: str, client_secret: str, user_id: int):
    async with aiosqlite.connect(config.DB_NAME) as db:
        await db.execute(
            'INSERT INTO stores (chat_id, store_name, client_id, client_secret, user_id) VALUES (?, ?, ?, ?, ?)',
            (chat_id, store_name, client_id, client_secret, user_id)
        )
        await db.commit()

async def get_all_stores() -> list:
    async with aiosqlite.connect(config.DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM stores') as cursor:
            return await cursor.fetchall()

async def get_stores_by_chat(chat_id: int) -> list:
    async with aiosqlite.connect(config.DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM stores WHERE chat_id = ?', (chat_id,)) as cursor:
            return await cursor.fetchall()

async def delete_store(store_id: int):
    async with aiosqlite.connect(config.DB_NAME) as db:
        await db.execute('DELETE FROM stores WHERE id = ?', (store_id,))
        await db.commit()

async def get_store_by_id(store_id: int):
    async with aiosqlite.connect(config.DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM stores WHERE id = ?', (store_id,)) as cursor:
            return await cursor.fetchone()