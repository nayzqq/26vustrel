import feedparser

import config
import db
import sentiment
from collectors import match_coins


def collect(aliases: dict):
    """Проходит по всем RSS-фидам из config.RSS_FEEDS, находит записи
    с упоминанием отслеживаемых монет и сохраняет их как сигналы."""
    new_count = 0
    for feed_url in config.RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"[rss] ошибка при парсинге {feed_url}: {e}")
            continue

        for entry in parsed.entries:
            title = getattr(entry, "title", "")
            link = getattr(entry, "link", "")
            summary = getattr(entry, "summary", "")
            full_text = f"{title} {summary}"

            coins = match_coins(full_text, aliases)
            if not coins:
                continue

            direction = sentiment.classify(full_text)
            for coin in coins:
                db.insert_signal(coin, "rss", "news", direction, title, link)
                new_count += 1

    return new_count
