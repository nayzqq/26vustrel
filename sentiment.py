"""
Грубая, но бесплатная и быстрая классификация текста по ключевым словам.
Это MVP-подход: без ML/LLM, работает по спискам маркеров роста/падения.
Дальше это легко заменить на вызов LLM для более качественной оценки.
"""

BULLISH_WORDS = [
    "surge", "soar", "rally", "bullish", "breakout", "all-time high", "ath",
    "moon", "pump", "upgrade", "buy", "long", "outperform", "record high",
    "adoption", "inflow", "growth", "gain", "rocket", "green",
    "рост", "растёт", "растет", "вырос", "покупать", "лонг", "пробой",
    "бычий", "ракета", "хай", "приток",
]

BEARISH_WORDS = [
    "crash", "plunge", "slump", "bearish", "sell-off", "selloff", "dump",
    "downgrade", "sell", "short", "underperform", "correction", "collapse",
    "outflow", "drop", "fall", "red", "liquidation", "fear",
    "падение", "падает", "упал", "продавать", "шорт", "медвежий", "обвал",
    "коррекция", "отток", "ликвидация",
]


def classify(text: str) -> str:
    """Возвращает 'up', 'down' или 'neutral' по количеству совпадений маркеров."""
    if not text:
        return "neutral"
    lowered = text.lower()
    bull_score = sum(1 for w in BULLISH_WORDS if w in lowered)
    bear_score = sum(1 for w in BEARISH_WORDS if w in lowered)

    if bull_score == bear_score:
        return "neutral"
    return "up" if bull_score > bear_score else "down"
