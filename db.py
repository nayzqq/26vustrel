import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coin TEXT NOT NULL,
    source TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('market', 'news', 'social')),
    direction TEXT NOT NULL CHECK(direction IN ('up', 'down', 'neutral')),
    text TEXT,
    url TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_signals_coin_time ON signals(coin, created_at);
CREATE INDEX IF NOT EXISTS idx_signals_category ON signals(coin, category, created_at);

-- защита от повторной вставки одной и той же новости/поста
-- (для рыночных сигналов url всегда уникален за счёт метки времени внутри него,
-- так что снапшоты метрик никогда не дедуплицируются между собой)
CREATE UNIQUE INDEX IF NOT EXISTS idx_signals_dedup ON signals(source, url);

CREATE TABLE IF NOT EXISTS alert_state (
    coin TEXT PRIMARY KEY,
    last_alert_at TEXT NOT NULL
);

-- сырые срезы рыночных метрик (цена/funding/OI), чтобы считать изменение
-- за скользящее окно, а не только текущее значение
CREATE TABLE IF NOT EXISTS market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    coin TEXT NOT NULL,
    exchange TEXT NOT NULL,
    price REAL,
    funding_rate REAL,
    open_interest REAL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_coin_time ON market_snapshots(coin, exchange, created_at);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def insert_signal(coin: str, source: str, category: str, direction: str, text: str, url: str):
    """Вставляет сигнал. Если такой (source, url) уже есть - молча игнорирует."""
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO signals (coin, source, category, direction, text, url, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (coin, source, category, direction, text, url, datetime.utcnow().isoformat()),
            )
        except sqlite3.IntegrityError:
            pass  # дубликат - пропускаем


def get_recent_signals(coin: str, window_minutes: int):
    since = (datetime.utcnow() - timedelta(minutes=window_minutes)).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM signals WHERE coin = ? AND created_at >= ? "
            "ORDER BY created_at DESC",
            (coin, since),
        ).fetchall()
    return rows


def get_tracked_coins():
    with get_conn() as conn:
        rows = conn.execute("SELECT DISTINCT coin FROM signals").fetchall()
    return [r["coin"] for r in rows]


def get_last_alert_time(coin: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_alert_at FROM alert_state WHERE coin = ?", (coin,)
        ).fetchone()
    return datetime.fromisoformat(row["last_alert_at"]) if row else None


def set_last_alert_time(coin: str):
    now = datetime.utcnow().isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO alert_state (coin, last_alert_at) VALUES (?, ?) "
            "ON CONFLICT(coin) DO UPDATE SET last_alert_at = excluded.last_alert_at",
            (coin, now),
        )


def insert_market_snapshot(coin: str, exchange: str, price: float, funding_rate: float, open_interest: float):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO market_snapshots (coin, exchange, price, funding_rate, open_interest, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (coin, exchange, price, funding_rate, open_interest, datetime.utcnow().isoformat()),
        )


def get_snapshot_near(coin: str, exchange: str, minutes_ago: int):
    """Берёт снапшот, ближайший к моменту 'minutes_ago назад' (с запасом ±50%
    окна, чтобы не промахнуться мимо интервала сбора)."""
    target = datetime.utcnow() - timedelta(minutes=minutes_ago)
    tolerance = timedelta(minutes=max(minutes_ago * 0.5, 5))
    low = (target - tolerance).isoformat()
    high = (target + tolerance).isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM market_snapshots WHERE coin = ? AND exchange = ? "
            "AND created_at BETWEEN ? AND ? "
            "ORDER BY ABS(julianday(created_at) - julianday(?)) ASC LIMIT 1",
            (coin, exchange, low, high, target.isoformat()),
        ).fetchone()
    return row


def prune_old(signal_hours: int = 48, snapshot_hours: int = 3):
    """Удаляет старые записи, чтобы файл базы не разрастался
    (особенно важно, когда база хранится в git-ветке между запусками)."""
    signals_cut = (datetime.utcnow() - timedelta(hours=signal_hours)).isoformat()
    snapshots_cut = (datetime.utcnow() - timedelta(hours=snapshot_hours)).isoformat()
    with get_conn() as conn:
        conn.execute("DELETE FROM signals WHERE created_at < ?", (signals_cut,))
        conn.execute("DELETE FROM market_snapshots WHERE created_at < ?", (snapshots_cut,))
