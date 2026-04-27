import aiohttp
from datetime import datetime, timedelta


def _to_float(val):
    try:
        return float(val)
    except:
        return 0.0


def _to_int(val):
    try:
        return int(float(val))
    except:
        return 0


async def get_avito_token(client_id, client_secret):
    url = "https://api.avito.ru/token"

    data = {
        "grant_type": "client_credentials",
        "client_id": client_id.strip(),
        "client_secret": client_secret.strip()
    }

    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False)
    ) as session:
        try:
            async with session.post(url, data=data) as resp:
                if resp.status == 200:
                    js = await resp.json()
                    return js.get("access_token")

                print(f"❌ TOKEN ERROR: {resp.status} | {await resp.text()}")

        except Exception as e:
            print(f"❌ TOKEN EXCEPTION: {e}")

    return None


async def get_avito_user_id(token):
    headers = {
        "Authorization": f"Bearer {token}"
    }

    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False)
    ) as session:
        try:
            async with session.get(
                "https://api.avito.ru/core/v1/accounts/self",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    return (await resp.json()).get("id")

                print(f"❌ USER_ID ERROR: {resp.status}")

        except Exception as e:
            print(f"❌ USER_ID EXCEPTION: {e}")

    return None


async def get_balance(token, user_id):
    headers = {
        "Authorization": f"Bearer {token}"
    }

    urls = [
        f"https://api.avito.ru/core/v1/accounts/{user_id}/balance/",
        f"https://api.avito.ru/core/v1/accounts/{user_id}/balance"
    ]

    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False)
    ) as session:
        for url in urls:
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        print(f"💰 BALANCE RAW: {data}")

                        return {
                            "wallet": _to_float(data.get("real")),
                            "advance": _to_float(data.get("bonus"))
                        }

                    print(f"❌ BALANCE ERROR: {resp.status} | {await resp.text()}")

            except Exception as e:
                print(f"❌ BALANCE EXCEPTION: {e}")

    return {
        "wallet": 0.0,
        "advance": 0.0
    }


async def get_all_item_ids(token):
    headers = {
        "Authorization": f"Bearer {token}"
    }

    all_ids = []

    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False)
    ) as session:
        for status in ["active", "old"]:
            for page in range(1, 20):
                try:
                    params = {
                        "per_page": 100,
                        "page": page,
                        "status": status
                    }

                    async with session.get(
                        "https://api.avito.ru/core/v1/items",
                        headers=headers,
                        params=params
                    ) as resp:
                        if resp.status != 200:
                            print(f"❌ ITEMS ERROR: {resp.status} | {await resp.text()}")
                            break

                        data = await resp.json()
                        items = data.get("resources", [])

                        if not items:
                            break

                        for item in items:
                            if item.get("id"):
                                all_ids.append(item["id"])

                except Exception as e:
                    print(f"❌ ITEMS EXCEPTION: {e}")
                    break

    return list(set(all_ids))


async def get_full_report_data(client_id, client_secret, user_id, today=None):
    if not today:
        today = datetime.now().date()

    token = await get_avito_token(client_id, client_secret)

    if not token:
        print("❌ NO TOKEN")
        return None

    all_ids = await get_all_item_ids(token)

    stats = {
        "today": {
            "views": 0,
            "contacts": 0,
            "spend": 0.0
        },
        "yesterday": {
            "views": 0,
            "contacts": 0,
            "spend": 0.0
        },
        "week": {
            "views": 0,
            "contacts": 0,
            "spend": 0.0
        }
    }

    if not all_ids:
        print("⚠️ Нет объявлений")

        return {
            "stats": stats,
            "token": token
        }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    date_from = today - timedelta(days=7)
    date_to = today

    async with aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=False)
    ) as session:
        chunks = [
            all_ids[i:i + 200]
            for i in range(0, len(all_ids), 200)
        ]

        for chunk in chunks:
            payload = {
                "dateFrom": date_from.isoformat(),
                "dateTo": date_to.isoformat(),
                "itemIds": chunk,
                "fields": [
                    "uniqViews",
                    "uniqContacts"
                ]
            }

            try:
                async with session.post(
                    f"https://api.avito.ru/stats/v1/accounts/{user_id}/items",
                    headers=headers,
                    json=payload
                ) as resp:
                    if resp.status != 200:
                        print(f"❌ STATS ERROR: {resp.status} | {await resp.text()}")
                        continue

                    data = await resp.json()

                    for item in data.get("result", {}).get("items", []):
                        for day in item.get("stats", []):
                            date = day.get("date")

                            views = _to_int(day.get("uniqViews"))
                            contacts = _to_int(day.get("uniqContacts"))

                            if date == today.isoformat():
                                stats["today"]["views"] += views
                                stats["today"]["contacts"] += contacts

                            if date == (today - timedelta(days=1)).isoformat():
                                stats["yesterday"]["views"] += views
                                stats["yesterday"]["contacts"] += contacts

                            stats["week"]["views"] += views
                            stats["week"]["contacts"] += contacts

            except Exception as e:
                print(f"❌ STATS EXCEPTION: {e}")

    return {
        "stats": stats,
        "token": token
    }