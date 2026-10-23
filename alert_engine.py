import html
from datetime import datetime, timedelta

import config
import db
from collectors import feargreed_collector


def _category_direction(rows, category: str):
    """Смотрит сигналы одной категории и решает, есть ли уверенное
    направление (up/down), по своим порогам min_signals/ratio."""
    thresholds = config.CATEGORY_THRESHOLDS[category]
    cat_rows = [r for r in rows if r["category"] == category]
    total = len(cat_rows)
    if total < thresholds["min_signals"]:
        return None, cat_rows

    up = sum(1 for r in cat_rows if r["direction"] == "up")
    down = sum(1 for r in cat_rows if r["direction"] == "down")
    if up == 0 and down == 0:
        return None, cat_rows

    up_ratio = up / total
    down_ratio = down / total

    if up_ratio >= thresholds["ratio"]:
        return "up", cat_rows
    if down_ratio >= thresholds["ratio"]:
        return "down", cat_rows
    return None, cat_rows


def check_alerts(tracked_tickers: list):
    """Для каждой монеты смотрит сигналы по категориям (market/news/social)
    за окно и алертит, только если минимум 2 РАЗНЫЕ категории сошлись
    в одном направлении. Так один разгорячённый сабреддит или одна
    новость не могут в одиночку вызвать алерт."""
    alerts = []
    categories = list(config.CATEGORY_THRESHOLDS.keys())

    for coin in tracked_tickers:
        rows = db.get_recent_signals(coin, config.ALERT_WINDOW_MINUTES)
        if not rows:
            continue

        category_result = {}
        for cat in categories:
            direction, cat_rows = _category_direction(rows, cat)
            if direction:
                category_result[cat] = (direction, cat_rows)

        for direction in ("up", "down"):
            matching_cats = [c for c, (d, _) in category_result.items() if d == direction]
            if len(matching_cats) < 2:
                continue

            last_alert = db.get_last_alert_time(coin)
            cooldown = timedelta(minutes=config.ALERT_COOLDOWN_MINUTES)
            if last_alert and datetime.utcnow() - last_alert < cooldown:
                continue  # кулдаун - не спамим повторно

            db.set_last_alert_time(coin)

            arrow = "🚀" if direction == "up" else "🔻"
            word = "РОСТ" if direction == "up" else "ПАДЕНИЕ"

            lines = [
                f"{arrow} <b>{coin}: подтверждённый сигнал на {word}</b>",
                f"Совпали категории: {', '.join(matching_cats)}",
                f"Fear & Greed Index: {feargreed_collector.get_cached_text()}",
                "",
            ]
            for cat in matching_cats:
                _, cat_rows = category_result[cat]
                examples = [r["text"] for r in cat_rows[:2] if r["text"]]
                lines.append(f"<b>{cat}:</b>")
                lines.extend(f"• {html.escape(e)}" for e in examples)

            alerts.append("\n".join(lines))
            break  # по этой монете за цикл - максимум один алерт

    return alerts
