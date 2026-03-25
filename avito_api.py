import aiohttp
import logging
from datetime import date

logger = logging.getLogger(__name__)


async def get_avito_token(client_id: str, client_secret: str) -> str | None:
    url = "https://api.avito.ru/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id.strip(),
        "client_secret": client_secret.strip()
    }

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        try:
            async with session.post(url, data=data) as response:
                result = await response.json()
                if response.status == 200:
                    return result.get("access_token")
                print(f"🛑 ОШИБКА ТОКЕНА: {response.status} - {result}")
                return None
        except Exception as e:
            logger.error(f"Ошибка сети (токен): {e}")
            return None


async def get_avito_user_id(token: str) -> int | None:
    url = "https://api.avito.ru/core/v1/accounts/self"
    headers = {"Authorization": f"Bearer {token}"}

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        try:
            async with session.get(url, headers=headers) as response:
                result = await response.json()
                if response.status == 200:
                    return result.get("id")
                return None
        except Exception:
            return None


async def get_balance(token: str) -> dict | None:
    url = "https://api.avito.ru/core/v1/accounts/self/balance"
    headers = {"Authorization": f"Bearer {token}"}

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "wallet": data.get("real", 0),
                        "advance": data.get("bonus", 0)
                    }
                return None
        except:
            return None


async def get_statistics(client_id: str, client_secret: str, user_id: int, date_from: date, date_to: date) -> dict | None:
    token = await get_avito_token(client_id, client_secret)
    if not token: return None
    url = f"https://api.avito.ru/stats/v1/accounts/{user_id}/items"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"dateFrom": date_from.isoformat(), "dateTo": date_to.isoformat(), "itemIds": []}

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        try:
            async with session.post(url, headers=headers, json=payload) as response:
                data = await response.json()

                if response.status != 200:
                    print(f"🛑 ОШИБКА API: {response.status} - {data}")
                    return None

                items_list = []
                if isinstance(data, list):
                    items_list = data
                elif isinstance(data, dict):
                    res = data.get("result", [])
                    if isinstance(res, list):
                        items_list = res
                    elif isinstance(res, dict):
                        items_list = res.get("items", [])

                v, c, s, calls, msgs = 0, 0, 0.0, 0, 0

                for item in items_list:
                    if not isinstance(item, dict): continue
                    st = item.get("stats", {})
                    if not isinstance(st, dict): continue

                    v += st.get("views", 0)
                    c += st.get("contacts", 0)
                    s += float(st.get("spend", 0.0))
                    calls += st.get("calls", 0)
                    msgs += st.get("messages", 0)

                return {
                    "views": v, "contacts": c, "spend": round(s, 2),
                    "cpv": round(s / v, 2) if v > 0 else 0,
                    "cpc": round(s / c, 2) if c > 0 else 0,
                    "calls": calls, "messages": msgs,
                    "token": token
                }
        except Exception as e:
            logger.error(f"Критическая ошибка парсинга: {e}")
            return None