"""
Alternative.me Fear & Greed Index - бесплатный, без ключа. Это ОБЩИЙ
рыночный индекс (не по конкретной монете), поэтому он не участвует как
отдельная "категория" в подтверждении алертов, а используется просто
как контекст в тексте уведомления: типа "экстремальный страх / жадность
на рынке" рядом с конкретным сигналом по монете.
"""
import requests

URL = "https://api.alternative.me/fng/"
REQUEST_TIMEOUT = 10

_cache = {"value": None, "label": None}


def fetch():
    try:
        resp = requests.get(URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        item = data["data"][0]
        _cache["value"] = int(item["value"])
        _cache["label"] = item["value_classification"]
    except (requests.RequestException, ValueError, KeyError, IndexError) as e:
        print(f"[feargreed] ошибка запроса: {e}")
    return _cache


def get_cached_text() -> str:
    """Короткая строка для вставки в текст алерта, например '72 (Greed)'."""
    if _cache["value"] is None:
        return "н/д"
    return f"{_cache['value']} ({_cache['label']})"
