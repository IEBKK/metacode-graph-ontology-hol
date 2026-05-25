"""SQLite 캐시/저장소 관리"""
import sqlite3
from contextlib import contextmanager
from market_prediction.config import DB_PATH


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    published TEXT,
    link TEXT UNIQUE,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market TEXT NOT NULL,
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume REAL,
    fetched_at TEXT NOT NULL,
    UNIQUE(market, symbol, date)
);

CREATE TABLE IF NOT EXISTS macro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator TEXT NOT NULL,
    date TEXT NOT NULL,
    value REAL,
    unit TEXT,
    fetched_at TEXT NOT NULL,
    UNIQUE(indicator, date)
);

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    target_date TEXT NOT NULL,
    prediction_json TEXT NOT NULL,
    model TEXT,
    input_hash TEXT
);

CREATE TABLE IF NOT EXISTS prediction_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prediction_id INTEGER REFERENCES predictions(id),
    scored_at TEXT NOT NULL,
    actual_json TEXT NOT NULL,
    accuracy_score REAL,
    notes TEXT
);
"""


@contextmanager
def get_db(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path=None):
    with get_db(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
