import logging

BOT_TOKEN = "ТОКЕН"
ADMIN_IDS = []
DB_NAME = "avito_stats.sqlite3"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)

try:
    from config_local import *
except ImportError:
    pass