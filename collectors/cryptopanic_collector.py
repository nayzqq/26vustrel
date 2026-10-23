import requests

import config
import db
import sentiment

API_URL = "https://cryptopanic.com/api/v1/posts/"


def _direction_from_votes(votes: dict, title: str) -> str:
    positive = votes.get("positive", 0)
    negative = votes.get("negative", 0)
    if positive == negative:
        # голосов мало/нет - fallback на ключевые слова в заголовке
        return sentiment.classify(title)
    return "up" if positive > negative else "down"


def collect(tracked_tickers: set):
    """Тянет свежие посты с CryptoPanic. currencies в ответе уже даёт тикер,
    поэтому отдельный поиск упоминаний по тексту не нужен."""
    if not config.CRYPTOPANIC_API_KEY:
        print("[cryptopanic] пропущено: не задан CRYPTOPANIC_API_KEY в .env")
        return 0

    params = {
        "auth_token": config.CRYPTOPANIC_API_KEY,
        "public": "true",
        "kind": "news",
    }
    try:
        resp = requests.get(API_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"[cryptopanic] ошибка запроса: {e}")
        return 0

    new_count = 0
    for post in data.get("results", []):
        title = post.get("title", "")
        url = post.get("url", "")
        currencies = post.get("currencies") or []
        votes = post.get("votes", {})

        direction = _direction_from_votes(votes, title)

        for currency in currencies:
            code = currency.get("code", "").upper()
            if code not in tracked_tickers:
                continue
            db.insert_signal(code, "cryptopanic", "news", direction, title, url)
            new_count += 1

    return new_count
