"""SQLite database layer for ETF Terminal."""

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / ".etf_terminal" / "data.db"


@dataclass
class Settings:
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_client_id: int = 1
    edgar_identity: str = ""
    cache_dir: str = str(Path.home() / ".etf_terminal" / "cache")
    freshness_days_fresh: int = 30
    freshness_days_acceptable: int = 90
    margin_warning_cushion: float = 0.15
    leverage_warning: float = 2.0
    export_dir: str = str(Path.home() / ".etf_terminal" / "exports")
    data_source: str = "auto"  # "auto", "edgar", "zacks"


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
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_tables(conn)
    return conn


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
    except Exception:
        pass


def load_settings() -> Settings:
    conn = get_db()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    s = Settings()
    for row in rows:
        if hasattr(s, row["key"]):
            attr_type = type(getattr(s, row["key"]))
            setattr(s, row["key"], attr_type(row["value"]))
    return s


def save_settings(s: Settings) -> None:
    conn = get_db()
    for k, v in s.__dict__.items():
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (k, str(v)),
        )
    conn.commit()
    conn.close()


def cache_etf(etf: CachedETF) -> None:
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO etf_cache VALUES (?, ?, ?, ?, ?, ?)",
        (etf.ticker, etf.cik, etf.series_id, etf.fund_name, etf.issuer, etf.last_updated),
    )
    conn.commit()
    conn.close()


def get_cached_etf(ticker: str) -> CachedETF | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM etf_cache WHERE ticker = ?", (ticker,)).fetchone()
    conn.close()
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
    conn.close()


def get_cached_holdings(ticker: str, source: str | None = None) -> dict | None:
    conn = get_db()
    if source:
        row = conn.execute("SELECT * FROM holdings_cache WHERE ticker = ? AND source = ?", (ticker, source)).fetchone()
    else:
        row = conn.execute("SELECT * FROM holdings_cache WHERE ticker = ? ORDER BY cached_at DESC", (ticker,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


# Watchlist operations
def add_to_watchlist(name: str, ticker: str) -> None:
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO watchlists VALUES (?, ?, ?)",
        (name, ticker, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def remove_from_watchlist(name: str, ticker: str) -> None:
    conn = get_db()
    conn.execute("DELETE FROM watchlists WHERE name = ? AND ticker = ?", (name, ticker))
    conn.commit()
    conn.close()


def get_watchlist(name: str) -> list[str]:
    conn = get_db()
    rows = conn.execute("SELECT ticker FROM watchlists WHERE name = ? ORDER BY added_at", (name,)).fetchall()
    conn.close()
    return [r["ticker"] for r in rows]


def get_all_watchlists() -> dict[str, list[str]]:
    conn = get_db()
    rows = conn.execute("SELECT DISTINCT name FROM watchlists ORDER BY name").fetchall()
    result = {}
    for r in rows:
        result[r["name"]] = get_watchlist(r["name"])
    conn.close()
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
    conn.close()
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
    conn.close()
    return [Note(**dict(r)) for r in rows]


def delete_note(note_id: int) -> None:
    conn = get_db()
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()


def search_cached_etfs(query: str) -> list[CachedETF]:
    """Search local ETF cache by fund_name or issuer (case-insensitive LIKE)."""
    conn = get_db()
    q = f"%{query}%"
    rows = conn.execute(
        "SELECT * FROM etf_cache WHERE fund_name LIKE ? OR issuer LIKE ? OR ticker LIKE ?",
        (q, q, q),
    ).fetchall()
    conn.close()
    return [CachedETF(**dict(r)) for r in rows]


# Sector cache operations
def cache_sector(ticker: str, sector: str) -> None:
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO sector_cache (ticker, sector, cached_at) VALUES (?, ?, ?)",
        (ticker.upper(), sector, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def get_cached_sector(ticker: str) -> str | None:
    conn = get_db()
    row = conn.execute("SELECT sector FROM sector_cache WHERE ticker = ?", (ticker.upper(),)).fetchone()
    conn.close()
    return row["sector"] if row else None


def get_cached_sectors_bulk(tickers: list[str]) -> dict[str, str]:
    if not tickers:
        return {}
    conn = get_db()
    placeholders = ",".join("?" * len(tickers))
    rows = conn.execute(
        f"SELECT ticker, sector FROM sector_cache WHERE ticker IN ({placeholders})",
        [t.upper() for t in tickers],
    ).fetchall()
    conn.close()
    return {row["ticker"]: row["sector"] for row in rows}
