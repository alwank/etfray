"""SQLite database layer for ETF Terminal."""

from __future__ import annotations

import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_log = logging.getLogger(__name__)

DB_PATH = Path.home() / ".etfray" / "data.db"

_db_lock = threading.Lock()
_db_conn: sqlite3.Connection | None = None


@dataclass
class Settings:
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_client_id: int = 1
    edgar_identity: str = ""
    cache_dir: str = str(Path.home() / ".etfray" / "cache")
    freshness_days_fresh: int = 30
    freshness_days_acceptable: int = 90
    margin_warning_cushion: float = 0.15
    leverage_warning: float = 2.0
    export_dir: str = str(Path.home() / ".etfray" / "exports")
    data_source: str = "auto"  # "auto", "edgar", "web"


@dataclass
class CachedETF:
    ticker: str
    cik: str = ""
    series_id: str = ""
    fund_name: str = ""
    issuer: str = ""
    last_updated: str = ""


@dataclass
class Note:
    id: int = 0
    target_type: str = ""  # "etf" or "portfolio"
    target_id: str = ""  # ticker or view name
    content: str = ""
    created_at: str = ""
    updated_at: str = ""


def get_db() -> sqlite3.Connection:
    global _db_conn
    with _db_lock:
        if _db_conn is not None:
            try:
                _db_conn.execute("SELECT 1")
            except sqlite3.ProgrammingError:
                # Stale singleton (e.g. legacy splash called .close() without reset)
                _db_conn = None
        if _db_conn is None:
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            _db_conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
            _db_conn.row_factory = sqlite3.Row
            _db_conn.execute("PRAGMA journal_mode=WAL")
            _init_tables(_db_conn)
        return _db_conn


def close_db() -> None:
    global _db_conn
    with _db_lock:
        if _db_conn is not None:
            _db_conn.close()
            _db_conn = None


def _init_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS etf_cache (
            ticker TEXT PRIMARY KEY,
            cik TEXT,
            series_id TEXT,
            fund_name TEXT,
            issuer TEXT,
            last_updated TEXT
        );
        CREATE TABLE IF NOT EXISTS holdings_cache (
            ticker TEXT NOT NULL,
            holdings_json TEXT,
            as_of_date TEXT,
            filed_date TEXT,
            source TEXT DEFAULT 'nport',
            cached_at TEXT,
            PRIMARY KEY (ticker, source)
        );
        CREATE TABLE IF NOT EXISTS watchlists (
            name TEXT NOT NULL,
            ticker TEXT NOT NULL,
            added_at TEXT,
            PRIMARY KEY (name, ticker)
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sector_cache (
            ticker TEXT PRIMARY KEY,
            sector TEXT NOT NULL,
            cached_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS etf_profile_cache (
            ticker TEXT PRIMARY KEY,
            profile_json TEXT NOT NULL,
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS price_history_cache (
            ticker TEXT NOT NULL,
            period TEXT NOT NULL,
            history_json TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY (ticker, period)
        );
        CREATE TABLE IF NOT EXISTS screener_cache (
            query_key  TEXT PRIMARY KEY,
            result_json TEXT NOT NULL,
            fetched_at  TEXT NOT NULL
        );
    """)
    # Migration: add source column if missing
    try:
        conn.execute("SELECT source FROM holdings_cache LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE holdings_cache ADD COLUMN source TEXT DEFAULT 'nport'")
    # Migration: convert old single-key holdings_cache to composite key
    try:
        cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='holdings_cache'")
        row = cur.fetchone()
        if row and "PRIMARY KEY (ticker, source)" not in row[0]:
            conn.executescript("""
                ALTER TABLE holdings_cache RENAME TO holdings_cache_old;
                CREATE TABLE holdings_cache (
                    ticker TEXT NOT NULL,
                    holdings_json TEXT,
                    as_of_date TEXT,
                    filed_date TEXT,
                    source TEXT DEFAULT 'nport',
                    cached_at TEXT,
                    PRIMARY KEY (ticker, source)
                );
                INSERT OR IGNORE INTO holdings_cache SELECT ticker, holdings_json, as_of_date, filed_date, COALESCE(source,'nport'), cached_at FROM holdings_cache_old;
                DROP TABLE holdings_cache_old;
            """)
    except Exception as exc:
        _log.warning("DB migration failed: %s", exc)
    # Migration: rename 'zacks' source to 'web'
    conn.execute("DELETE FROM holdings_cache WHERE source = 'zacks'")
    conn.execute("UPDATE settings SET value = 'web' WHERE key = 'data_source' AND value = 'zacks'")
    conn.commit()


def load_settings() -> Settings:
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    s = Settings()
    for row in rows:
        if hasattr(s, row["key"]):
            attr_type = type(getattr(s, row["key"]))
            try:
                setattr(s, row["key"], attr_type(row["value"]))
            except (ValueError, TypeError):
                pass  # keep dataclass default
    return s


def save_settings(s: Settings) -> None:
    conn = get_db()
    for k, v in s.__dict__.items():
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (k, str(v)),
        )
    conn.commit()


def cache_etf(etf: CachedETF) -> None:
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO etf_cache VALUES (?, ?, ?, ?, ?, ?)",
        (etf.ticker, etf.cik, etf.series_id, etf.fund_name, etf.issuer, etf.last_updated),
    )
    conn.commit()


def get_cached_etf(ticker: str) -> CachedETF | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM etf_cache WHERE ticker = ?", (ticker,)).fetchone()
    if row:
        return CachedETF(**dict(row))
    return None


def cache_holdings(ticker: str, holdings_json: str, as_of_date: str, filed_date: str, source: str = "nport") -> None:
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO holdings_cache VALUES (?, ?, ?, ?, ?, ?)",
        (ticker, holdings_json, as_of_date, filed_date, source, datetime.now().isoformat()),
    )
    conn.commit()


def get_cached_holdings(ticker: str, source: str | None = None) -> dict | None:
    conn = get_db()
    if source:
        row = conn.execute("SELECT * FROM holdings_cache WHERE ticker = ? AND source = ?", (ticker, source)).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM holdings_cache WHERE ticker = ? ORDER BY cached_at DESC", (ticker,)
        ).fetchone()
    if row:
        return dict(row)
    return None


# Watchlist operations
def is_in_watchlist(name: str, ticker: str) -> bool:
    conn = get_db()
    row = conn.execute(
        "SELECT 1 FROM watchlists WHERE name = ? AND ticker = ?",
        (name, ticker),
    ).fetchone()
    return row is not None


def add_to_watchlist(name: str, ticker: str) -> bool:
    """Add ticker to watchlist. Returns True if newly added, False if duplicate."""
    conn = get_db()
    cursor = conn.execute(
        "INSERT OR IGNORE INTO watchlists VALUES (?, ?, ?)",
        (name, ticker, datetime.now().isoformat()),
    )
    added = cursor.rowcount > 0
    conn.commit()
    return added


def remove_from_watchlist(name: str, ticker: str) -> None:
    conn = get_db()
    conn.execute("DELETE FROM watchlists WHERE name = ? AND ticker = ?", (name, ticker))
    conn.commit()


def get_watchlist(name: str) -> list[str]:
    conn = get_db()
    rows = conn.execute("SELECT ticker FROM watchlists WHERE name = ? ORDER BY added_at", (name,)).fetchall()
    return [r["ticker"] for r in rows]


def get_all_watchlists() -> dict[str, list[str]]:
    conn = get_db()
    rows = conn.execute("SELECT name, ticker FROM watchlists ORDER BY name, added_at").fetchall()
    result: dict[str, list[str]] = {}
    for r in rows:
        result.setdefault(r["name"], []).append(r["ticker"])
    return result


# Notes operations
def save_note(note: Note) -> int:
    conn = get_db()
    now = datetime.now().isoformat()
    if note.id:
        conn.execute(
            "UPDATE notes SET content = ?, updated_at = ? WHERE id = ?",
            (note.content, now, note.id),
        )
    else:
        cur = conn.execute(
            "INSERT INTO notes (target_type, target_id, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (note.target_type, note.target_id, note.content, now, now),
        )
        note.id = cur.lastrowid
    conn.commit()
    return note.id


def get_notes(target_type: str = "", target_id: str = "") -> list[Note]:
    conn = get_db()
    query = "SELECT * FROM notes WHERE 1=1"
    params: list = []
    if target_type:
        query += " AND target_type = ?"
        params.append(target_type)
    if target_id:
        query += " AND target_id = ?"
        params.append(target_id)
    query += " ORDER BY updated_at DESC"
    rows = conn.execute(query, params).fetchall()
    return [Note(**dict(r)) for r in rows]


def delete_note(note_id: int) -> None:
    conn = get_db()
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()


def get_note(target_type: str, target_id: str) -> Note | None:
    """Return the most-recent note matching (target_type, target_id), or None."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM notes WHERE target_type = ? AND target_id = ? ORDER BY updated_at DESC LIMIT 1",
        (target_type, target_id),
    ).fetchone()
    if row:
        return Note(**dict(row))
    return None


def upsert_note(target_type: str, target_id: str, content: str) -> None:
    """Insert or update the single canonical note for (target_type, target_id)."""
    now = datetime.now().isoformat()
    conn = get_db()
    row = conn.execute(
        "SELECT id FROM notes WHERE target_type = ? AND target_id = ?",
        (target_type, target_id),
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE notes SET content = ?, updated_at = ? WHERE id = ?",
            (content, now, row["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO notes (target_type, target_id, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (target_type, target_id, content, now, now),
        )
    conn.commit()


def get_cached_issuers() -> list[str]:
    """Return distinct non-empty issuers from local ETF cache."""
    conn = get_db()
    rows = conn.execute(
        "SELECT DISTINCT issuer FROM etf_cache WHERE issuer IS NOT NULL AND issuer != '' ORDER BY issuer",
    ).fetchall()
    return [r["issuer"] for r in rows]


def search_cached_etfs(query: str) -> list[CachedETF]:
    """Search local ETF cache by fund_name or issuer (case-insensitive LIKE)."""
    conn = get_db()
    q = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM etf_cache WHERE fund_name LIKE ? OR issuer LIKE ? OR ticker LIKE ?",
        (q, q, q),
    ).fetchall()
    return [CachedETF(**dict(r)) for r in rows]


# Sector cache operations
def cache_sector(ticker: str, sector: str) -> None:
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO sector_cache (ticker, sector, cached_at) VALUES (?, ?, ?)",
        (ticker.upper(), sector, datetime.now().isoformat()),
    )
    conn.commit()


def get_cached_sector(ticker: str, ttl_days: int = 90) -> str | None:
    from datetime import timedelta

    conn = get_db()
    cutoff = (datetime.now() - timedelta(days=ttl_days)).isoformat()
    row = conn.execute(
        "SELECT sector FROM sector_cache WHERE ticker = ? AND cached_at > ?",
        (ticker.upper(), cutoff),
    ).fetchone()
    return row["sector"] if row else None


def get_cached_sectors_bulk(tickers: list[str], ttl_days: int = 90) -> dict[str, str]:
    if not tickers:
        return {}
    from datetime import timedelta

    conn = get_db()
    cutoff = (datetime.now() - timedelta(days=ttl_days)).isoformat()
    placeholders = ",".join("?" * len(tickers))
    rows = conn.execute(
        f"SELECT ticker, sector FROM sector_cache WHERE ticker IN ({placeholders}) AND cached_at > ?",
        [t.upper() for t in tickers] + [cutoff],
    ).fetchall()
    return {row["ticker"]: row["sector"] for row in rows}


def get_holdings_count_bulk(tickers: list[str]) -> dict[str, int]:
    """Return {ticker: holdings_count} for all tickers that have cached holdings.

    Uses SQLite's json_array_length to count rows without loading the full JSON.
    """
    if not tickers:
        return {}
    conn = get_db()
    placeholders = ",".join("?" * len(tickers))
    # holdings_json is stored as a pandas DataFrame to_json() dict-of-dicts:
    # {"col_name": {"0": val, "1": val, ...}} — count the keys of any inner object.
    # Multiple sources may exist per ticker; take the MAX count.
    rows = conn.execute(
        f"SELECT h.ticker, MAX(("
        f"  SELECT COUNT(*) FROM json_each(json_extract(h.holdings_json, '$.'||("
        f"    SELECT key FROM json_each(h.holdings_json) LIMIT 1"
        f"  )))"
        f")) AS cnt "
        f"FROM holdings_cache h "
        f"WHERE h.ticker IN ({placeholders}) "
        f"AND h.holdings_json IS NOT NULL "
        f"GROUP BY h.ticker",
        [t.upper() for t in tickers],
    ).fetchall()
    return {row["ticker"]: row["cnt"] for row in rows if row["cnt"]}


# ETF profile cache (Yahoo Finance / yfinance)
def cache_etf_profile(ticker: str, profile_json: str, fetched_at: str) -> None:
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO etf_profile_cache (ticker, profile_json, fetched_at) VALUES (?, ?, ?)",
        (ticker.upper(), profile_json, fetched_at),
    )
    conn.commit()


def get_cached_etf_profile(ticker: str) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM etf_profile_cache WHERE ticker = ?", (ticker.upper(),)).fetchone()
    if row:
        return dict(row)
    return None


def get_all_cached_profiles() -> dict[str, str]:
    """Return all cached ETF profiles as {ticker: profile_json} in one DB query."""
    conn = get_db()
    rows = conn.execute("SELECT ticker, profile_json FROM etf_profile_cache").fetchall()
    return {row[0]: row[1] for row in rows if row[1]}


# Price history cache (Yahoo Finance / yfinance)
def cache_price_history(ticker: str, period: str, history_json: str, fetched_at: str) -> None:
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO price_history_cache (ticker, period, history_json, fetched_at) VALUES (?, ?, ?, ?)",
        (ticker.upper(), period, history_json, fetched_at),
    )
    conn.commit()


def get_cached_price_history(ticker: str, period: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM price_history_cache WHERE ticker = ? AND period = ?",
        (ticker.upper(), period),
    ).fetchone()
    if row:
        return dict(row)
    return None


# Screener cache (Yahoo Finance yf.screen results)
def cache_screener_result(query_key: str, result_json: str, fetched_at: str) -> None:
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO screener_cache (query_key, result_json, fetched_at) VALUES (?, ?, ?)",
        (query_key, result_json, fetched_at),
    )
    conn.commit()


def get_cached_screener_result(query_key: str) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM screener_cache WHERE query_key = ?",
        (query_key,),
    ).fetchone()
    if row:
        return dict(row)
    return None
