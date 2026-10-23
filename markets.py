"""
Получаем актуальный топ-10 монет по капитализации через публичный
CoinGecko API (ключ не нужен). Результат кэшируем на диск на 24 часа,
чтобы не дёргать API на каждый цикл сборщика.
"""
import json
import os
import time
import requests

CACHE_FILE = "top10_cache.json"
CACHE_TTL_SECONDS = 24 * 60 * 60

COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&order=market_cap_desc&per_page=10&page=1"
)


def _fetch_from_api() -> dict:
    resp = requests.get(COINGECKO_URL, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    aliases = {}
    for coin in data:
        symbol = coin["symbol"].upper()
        name = coin["name"].lower()
        aliases[symbol] = list({symbol.lower(), name})
    return aliases


def get_top10_aliases(fallback: dict) -> dict:
    """Возвращает {TICKER: [варианты упоминания в тексте]}.
    При ошибке сети / API — используем fallback-список из config.py."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if time.time() - cached.get("ts", 0) < CACHE_TTL_SECONDS:
                return cached["aliases"]
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    try:
        aliases = _fetch_from_api()
    except (requests.RequestException, ValueError, KeyError):
        return fallback

    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"ts": time.time(), "aliases": aliases}, f)
    except OSError:
        pass

    return aliases
