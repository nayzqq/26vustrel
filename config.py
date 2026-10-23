import os
from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    # пустая строка (например, незаданная переменная в GitHub Actions) = "не задано"
    value = os.getenv(name)
    return int(value) if value else default


def _float(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value else default


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = os.getenv("REDDIT_USER_AGENT") or "futures-sentiment-bot"

CRYPTOPANIC_API_KEY = os.getenv("CRYPTOPANIC_API_KEY", "")

ALERT_WINDOW_MINUTES = _int("ALERT_WINDOW_MINUTES", 20)
ALERT_COOLDOWN_MINUTES = _int("ALERT_COOLDOWN_MINUTES", 60)
COLLECT_INTERVAL_SECONDS = _int("COLLECT_INTERVAL_SECONDS", 300)

# Reddit по умолчанию выключен (self-service API сейчас недоступен, см. README).
# Если у тебя когда-нибудь появится одобренный доступ - включи флагом в .env.
ENABLE_REDDIT = os.getenv("ENABLE_REDDIT", "false").lower() == "true"

# --- Пороги подтверждения по категориям сигналов ---
# Алерт срабатывает, только если минимум 2 РАЗНЫЕ категории (market/news/social)
# сошлись в одном направлении - это резко снижает число ложных срабатываний
# по сравнению с одним источником.
CATEGORY_THRESHOLDS = {
    "market": {
        "min_signals": _int("MARKET_MIN_SIGNALS", 1),
        "ratio": _float("MARKET_RATIO_THRESHOLD", 0.6),
    },
    "news": {
        "min_signals": _int("NEWS_MIN_SIGNALS", 5),
        "ratio": _float("NEWS_RATIO_THRESHOLD", 0.65),
    },
    "social": {
        "min_signals": _int("SOCIAL_MIN_SIGNALS", 5),
        "ratio": _float("SOCIAL_RATIO_THRESHOLD", 0.65),
    },
}

# --- Пороги для рыночных метрик (биржевые данные) ---
# На сколько % должна измениться цена/OI внутри ALERT_WINDOW_MINUTES,
# чтобы это считалось "резким" движением
MARKET_PRICE_SPIKE_PCT = _float("MARKET_PRICE_SPIKE_PCT", 2.5)
MARKET_OI_SPIKE_PCT = _float("MARKET_OI_SPIKE_PCT", 5.0)
# Абсолютное значение funding rate (в %), которое уже считается экстремальным
MARKET_FUNDING_EXTREME_PCT = _float("MARKET_FUNDING_EXTREME_PCT", 0.05)

DB_PATH = os.getenv("DB_PATH") or "futures_bot.db"

# Источники новостей (RSS). Можно свободно добавлять/убирать.
RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
]

# Сабреддиты для мониторинга
SUBREDDITS = ["CryptoCurrency", "CryptoMarkets", "Bitcoin", "ethtrader"]

# Тикер -> варианты упоминания в тексте (для поиска по заголовкам)
COIN_ALIASES = {
    "BTC": ["btc", "bitcoin", "биткоин", "биткойн"],
    "ETH": ["eth", "ethereum", "эфириум", "эфир"],
    "BNB": ["bnb", "binance coin"],
    "SOL": ["sol", "solana", "солана"],
    "XRP": ["xrp", "ripple"],
    "ADA": ["ada", "cardano", "кардано"],
    "DOGE": ["doge", "dogecoin", "доджкоин"],
    "TON": ["ton", "toncoin"],
    "TRX": ["trx", "tron"],
    "AVAX": ["avax", "avalanche"],
}
