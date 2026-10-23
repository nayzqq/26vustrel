"""
Собирает объективные рыночные метрики по фьючерсам напрямую с бирж:
цену, funding rate, open interest. Публичные эндпоинты, ключ не нужен.

Bybit - основной источник (обычно не блокирует облачные IP).
OKX - fallback, если Bybit недоступен для конкретной монеты/региона.

Важно: Binance сознательно не используется как источник данных для
самого бота (в отличие от справки в README про биржи вообще) - Binance
часто отдаёт 451 "restricted location" для IP облачных дата-центров
(Oracle Cloud, AWS и т.п.), что сделает бота нестабильным именно на
том хостинге, который мы планируем использовать.
"""
import time
from datetime import datetime

import requests

import config
import db

BYBIT_TICKERS_URL = "https://api.bybit.com/v5/market/tickers"
OKX_TICKER_URL = "https://www.okx.com/api/v5/market/ticker"
OKX_FUNDING_URL = "https://www.okx.com/api/v5/public/funding-rate"
OKX_OI_URL = "https://www.okx.com/api/v5/public/open-interest"

REQUEST_TIMEOUT = 10


def _fetch_bybit(coin: str):
    symbol = f"{coin}USDT"
    try:
        resp = requests.get(
            BYBIT_TICKERS_URL,
            params={"category": "linear", "symbol": symbol},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("result", {}).get("list", [])
        if not items:
            return None
        item = items[0]
        return {
            "price": float(item["lastPrice"]),
            "funding_rate": float(item["fundingRate"]) * 100,  # доля -> %
            "open_interest": float(item["openInterest"]),
        }
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def _fetch_okx(coin: str):
    inst_id = f"{coin}-USDT-SWAP"
    try:
        price_resp = requests.get(
            OKX_TICKER_URL, params={"instId": inst_id}, timeout=REQUEST_TIMEOUT
        )
        price_resp.raise_for_status()
        price_data = price_resp.json().get("data", [])
        if not price_data:
            return None
        price = float(price_data[0]["last"])

        funding_resp = requests.get(
            OKX_FUNDING_URL, params={"instId": inst_id}, timeout=REQUEST_TIMEOUT
        )
        funding_resp.raise_for_status()
        funding_data = funding_resp.json().get("data", [])
        funding_rate = float(funding_data[0]["fundingRate"]) * 100 if funding_data else 0.0

        oi_resp = requests.get(
            OKX_OI_URL, params={"instId": inst_id}, timeout=REQUEST_TIMEOUT
        )
        oi_resp.raise_for_status()
        oi_data = oi_resp.json().get("data", [])
        open_interest = float(oi_data[0]["oi"]) if oi_data else None

        return {"price": price, "funding_rate": funding_rate, "open_interest": open_interest}
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
        return None


def _get_metrics(coin: str):
    """Пробует Bybit, при неудаче - OKX. Возвращает (exchange, metrics) или (None, None)."""
    metrics = _fetch_bybit(coin)
    if metrics is not None:
        return "bybit", metrics
    metrics = _fetch_okx(coin)
    if metrics is not None:
        return "okx", metrics
    return None, None


def _make_url(exchange: str, coin: str, metric: str) -> str:
    # уникальный "url" на каждый снимок, чтобы не попасть под dedup-индекс -
    # рыночные метрики не дублируются, каждая новая точка во времени важна
    return f"market://{exchange}/{coin}/{metric}/{time.time_ns()}"


def collect(tracked_tickers: set):
    new_count = 0

    for coin in tracked_tickers:
        exchange, metrics = _get_metrics(coin)
        if metrics is None:
            print(f"[market] {coin}: не удалось получить данные ни с Bybit, ни с OKX")
            continue

        db.insert_market_snapshot(
            coin, exchange, metrics["price"], metrics["funding_rate"], metrics["open_interest"]
        )

        prev = db.get_snapshot_near(coin, exchange, config.ALERT_WINDOW_MINUTES)
        if prev is None:
            continue  # пока не с чем сравнивать - наберём историю на следующих циклах

        price_change_pct = None
        if prev["price"]:
            price_change_pct = (metrics["price"] - prev["price"]) / prev["price"] * 100

        oi_change_pct = None
        if prev["open_interest"] and metrics["open_interest"] is not None:
            oi_change_pct = (
                (metrics["open_interest"] - prev["open_interest"]) / prev["open_interest"] * 100
            )

        funding_now = metrics["funding_rate"]

        # 1) резкое движение цены
        if price_change_pct is not None and abs(price_change_pct) >= config.MARKET_PRICE_SPIKE_PCT:
            direction = "up" if price_change_pct > 0 else "down"
            text = f"Цена {coin} изменилась на {price_change_pct:+.2f}% за {config.ALERT_WINDOW_MINUTES} мин ({exchange})"
            db.insert_signal(coin, exchange, "market", direction, text, _make_url(exchange, coin, "price"))
            new_count += 1

        # 2) резкий рост/падение open interest - используем направление цены,
        # чтобы понять, новые ли это лонги/шорты или закрытие позиций
        if (
            oi_change_pct is not None
            and abs(oi_change_pct) >= config.MARKET_OI_SPIKE_PCT
            and price_change_pct is not None
            and price_change_pct != 0
        ):
            direction = "up" if price_change_pct > 0 else "down"
            text = (
                f"Open Interest {coin} изменился на {oi_change_pct:+.2f}% за "
                f"{config.ALERT_WINDOW_MINUTES} мин, цена {price_change_pct:+.2f}% ({exchange})"
            )
            db.insert_signal(coin, exchange, "market", direction, text, _make_url(exchange, coin, "oi"))
            new_count += 1

        # 3) экстремальный funding rate - перекос толпы в одну сторону
        if abs(funding_now) >= config.MARKET_FUNDING_EXTREME_PCT:
            direction = "up" if funding_now > 0 else "down"
            text = f"Funding rate {coin} экстремальный: {funding_now:+.3f}% ({exchange})"
            db.insert_signal(coin, exchange, "market", direction, text, _make_url(exchange, coin, "funding"))
            new_count += 1

    return new_count


def probe() -> dict:
    """Одна пробная проверка доступности бирж с текущего IP (для логов).
    Нужна, чтобы сразу видеть, не блокирует ли биржа IP облачного раннера."""
    result = {}
    checks = {
        "bybit": (BYBIT_TICKERS_URL, {"category": "linear", "symbol": "BTCUSDT"}),
        "okx": (OKX_TICKER_URL, {"instId": "BTC-USDT-SWAP"}),
    }
    for name, (url, params) in checks.items():
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
            result[name] = f"HTTP {resp.status_code}"
        except requests.RequestException as e:
            result[name] = type(e).__name__
    return result
