import config
import db
import sentiment
from collectors import match_coins

_reddit = None


def _get_client():
    global _reddit
    if _reddit is None:
        if not (config.REDDIT_CLIENT_ID and config.REDDIT_CLIENT_SECRET):
            return None
        import praw  # ленивый импорт: без Reddit пакет praw не нужен

        _reddit = praw.Reddit(
            client_id=config.REDDIT_CLIENT_ID,
            client_secret=config.REDDIT_CLIENT_SECRET,
            user_agent=config.REDDIT_USER_AGENT,
        )
    return _reddit


def collect(aliases: dict, limit_per_sub: int = 25):
    """Смотрит свежие посты в отслеживаемых сабреддитах.

    ВАЖНО: с ноября 2025 Reddit закрыл self-service выдачу API-ключей
    (Responsible Builder Policy) - для личных некоммерческих ботов
    получить одобрение практически нереально. Поэтому по умолчанию этот
    коллектор выключен флагом ENABLE_REDDIT в .env. Если у тебя есть
    одобренный доступ - включи флаг и заполни ключи."""
    if not config.ENABLE_REDDIT:
        return 0

    reddit = _get_client()
    if reddit is None:
        print("[reddit] пропущено: не заданы REDDIT_CLIENT_ID/SECRET в .env")
        return 0

    new_count = 0
    for sub_name in config.SUBREDDITS:
        try:
            subreddit = reddit.subreddit(sub_name)
            for post in subreddit.new(limit=limit_per_sub):
                full_text = f"{post.title} {post.selftext or ''}"
                coins = match_coins(full_text, aliases)
                if not coins:
                    continue

                direction = sentiment.classify(full_text)
                url = f"https://reddit.com{post.permalink}"
                for coin in coins:
                    db.insert_signal(coin, "reddit", "social", direction, post.title, url)
                    new_count += 1
        except Exception as e:
            print(f"[reddit] ошибка при чтении r/{sub_name}: {e}")
            continue

    return new_count
