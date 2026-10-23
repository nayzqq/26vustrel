"""
Один цикл работы бота: собрать данные -> проверить алерты -> отправить -> выйти.
Используется в GitHub Actions (там нет постоянного процесса, запуск по расписанию).
Локально можно проверить так:  python run_once.py
"""
import logging

import requests

import alert_engine
import config
import db
import markets
from collectors import (
    cryptopanic_collector,
    feargreed_collector,
    market_collector,
    reddit_collector,
    rss_collector,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("futures-bot.run_once")


def send_telegram(text: str) -> bool:
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        logger.warning("Не заданы TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID, алерт не отправлен:\n%s", text)
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
    except requests.RequestException as e:
        # в лог пишем только тип ошибки: текст исключения может содержать URL с токеном
        logger.error("Не удалось отправить алерт в Telegram: %s", type(e).__name__)
        return False
    if resp.status_code != 200:
        logger.error("Telegram вернул HTTP %s: %s", resp.status_code, resp.text[:200])
        return False
    return True


def main():
    db.init_db()

    logger.info("Доступность бирж с этого IP: %s", market_collector.probe())

    aliases = markets.get_top10_aliases(fallback=config.COIN_ALIASES)
    tracked = set(aliases.keys())

    market_n = market_collector.collect(tracked)
    rss_n = rss_collector.collect(aliases)
    cp_n = cryptopanic_collector.collect(tracked)
    reddit_n = reddit_collector.collect(aliases)
    feargreed_collector.fetch()

    logger.info(
        "Собрано сигналов: market=%d rss=%d cryptopanic=%d reddit=%d",
        market_n, rss_n, cp_n, reddit_n,
    )

    alerts = alert_engine.check_alerts(sorted(tracked))
    for text in alerts:
        ok = send_telegram(text)
        logger.info("Алерт %s: %s", "отправлен" if ok else "НЕ отправлен", text.splitlines()[0])

    if not alerts:
        logger.info("Алертов нет (нужно совпадение минимум 2 категорий сигналов).")

    db.prune_old()


if __name__ == "__main__":
    main()
