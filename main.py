import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import db
import markets
import alert_engine
from collectors import (
    rss_collector,
    reddit_collector,
    cryptopanic_collector,
    market_collector,
    feargreed_collector,
)
from bot import bot, dp, send_alert

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("futures-bot.main")


async def collect_and_check():
    aliases = markets.get_top10_aliases(fallback=config.COIN_ALIASES)
    tracked_tickers = set(aliases.keys())

    rss_n = rss_collector.collect(aliases)
    reddit_n = reddit_collector.collect(aliases)
    cp_n = cryptopanic_collector.collect(tracked_tickers)
    market_n = market_collector.collect(tracked_tickers)
    feargreed_collector.fetch()

    logger.info(
        "Собрано сигналов: market=%d rss=%d cryptopanic=%d reddit=%d",
        market_n, rss_n, cp_n, reddit_n,
    )

    alerts = alert_engine.check_alerts(list(tracked_tickers))
    for text in alerts:
        await send_alert(text)
        logger.info("Отправлен алерт: %s", text.splitlines()[0])


async def main():
    db.init_db()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        collect_and_check,
        "interval",
        seconds=config.COLLECT_INTERVAL_SECONDS,
        next_run_time=None,
    )
    scheduler.start()

    # первый сбор сразу при старте, не дожидаясь первого интервала
    await collect_and_check()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
