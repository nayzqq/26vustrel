def match_coins(text: str, aliases: dict) -> list:
    """Возвращает список тикеров, упомянутых в тексте, по словарю алиасов
    вида {"BTC": ["btc", "bitcoin", ...], ...}."""
    if not text:
        return []
    lowered = text.lower()
    found = []
    for ticker, variants in aliases.items():
        for variant in variants:
            if variant in lowered:
                found.append(ticker)
                break
    return found
