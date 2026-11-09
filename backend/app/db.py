"""SQLite persistence layer. Schema mirrors the Strategic Opportunities Tracker workbook."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Iterable

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  country TEXT, domain TEXT, segment TEXT, counterparty TEXT, type TEXT,
  sponsor TEXT, owner TEXT,
  priority INTEGER DEFAULT 3,
  commercial INTEGER DEFAULT 3,
  value REAL DEFAULT 0,
  status TEXT, outlook TEXT, rationale TEXT, latest TEXT,
  last_engagement TEXT, milestone TEXT, milestone_date TEXT,
  next_action TEXT, action_owner TEXT,
  intervention TEXT DEFAULT 'No',
  announce TEXT DEFAULT 'No',
  target_announcement TEXT,
  sensitivity TEXT DEFAULT 'Confidential',
  verified TEXT, source TEXT,
  lat REAL, lon REAL,
  site TEXT,
  competitors INTEGER DEFAULT 0,
  created TEXT, closed TEXT
);
CREATE TABLE IF NOT EXISTS engagements (
  id TEXT PRIMARY KEY,
  opp TEXT REFERENCES opportunities(id) ON DELETE CASCADE,
  date TEXT, type TEXT, external TEXT, internal TEXT,
  summary TEXT, commitments TEXT, follow_up TEXT, owner TEXT, due TEXT,
  source TEXT DEFAULT 'manual'
);
CREATE TABLE IF NOT EXISTS actions (
  id TEXT PRIMARY KEY,
  opp TEXT REFERENCES opportunities(id) ON DELETE CASCADE,
  title TEXT, category TEXT, owner TEXT, due TEXT, status TEXT,
  priority TEXT, blocker TEXT, escalate TEXT DEFAULT 'No', update_note TEXT,
  created TEXT
);
CREATE TABLE IF NOT EXISTS announcements (
  id TEXT PRIMARY KEY,
  opp TEXT REFERENCES opportunities(id) ON DELETE CASCADE,
  title TEXT, type TEXT, target TEXT, event TEXT, lead TEXT,
  readiness TEXT, legal TEXT, ir TEXT, counterparty TEXT, disclose TEXT
);
CREATE TABLE IF NOT EXISTS discussions (
  id TEXT PRIMARY KEY,
  opp TEXT REFERENCES opportunities(id) ON DELETE CASCADE,
  parent TEXT,
  author TEXT, body TEXT, created TEXT,
  source TEXT DEFAULT 'precast',
  external_id TEXT,
  web_url TEXT
);
CREATE INDEX IF NOT EXISTS ix_disc_opp ON discussions(opp);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY, value TEXT
);
CREATE TABLE IF NOT EXISTS ai_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  at TEXT, kind TEXT, ref TEXT, prompt TEXT, output TEXT, engine TEXT
);
CREATE INDEX IF NOT EXISTS ix_eng_opp ON engagements(opp);
CREATE INDEX IF NOT EXISTS ix_act_opp ON actions(opp);
CREATE INDEX IF NOT EXISTS ix_ann_opp ON announcements(opp);
"""

# Columns added after v1; applied to existing databases on start.
MIGRATIONS = [("opportunities", "teams_channel_id TEXT"), ("opportunities", "teams_web_url TEXT"),
              ("opportunities", "sharepoint_url TEXT"), ("engagements", "link TEXT")]

TABLE_COLUMNS: dict[str, list[str]] = {}
_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA foreign_keys = ON")
        _conn.executescript(SCHEMA)
        for table, col in MIGRATIONS:
            existing = {r[1] for r in _conn.execute(f"PRAGMA table_info({table})")}
            if col.split()[0] not in existing:
                _conn.execute(f"ALTER TABLE {table} ADD COLUMN {col}")
        _conn.commit()
        for t in ("opportunities", "engagements", "actions", "announcements", "discussions"):
            TABLE_COLUMNS[t] = [r[1] for r in _conn.execute(f"PRAGMA table_info({t})")]
    return _conn


def reset_connection(path: str | None = None) -> None:
    """Used by tests to point at a fresh database file."""
    global _conn
    from . import config

    with _lock:
        if _conn is not None:
            _conn.close()
        _conn = None
        if path:
            config.DB_PATH = __import__("pathlib").Path(path)
            globals()["DB_PATH"] = config.DB_PATH


@contextmanager
def tx():
    with _lock:
        c = _connect()
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise


def _norm(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    return v


def all_rows(table: str, where: str = "", params: Iterable[Any] = ()) -> list[dict]:
    with tx() as c:
        sql = f"SELECT * FROM {table}" + (f" WHERE {where}" if where else "")
        return [dict(r) for r in c.execute(sql, tuple(params))]


def get_row(table: str, rid: str) -> dict | None:
    with tx() as c:
        r = c.execute(f"SELECT * FROM {table} WHERE id = ?", (rid,)).fetchone()
        return dict(r) if r else None


def upsert(table: str, row: dict) -> dict:
    _connect()
    cols = [k for k in row if k in TABLE_COLUMNS[table]]
    if "id" not in cols:
        raise ValueError("Row needs an id")
    vals = [_norm(row[k]) for k in cols]
    updates = ", ".join(f"{k}=excluded.{k}" for k in cols if k != "id")
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) "
        f"ON CONFLICT(id) DO UPDATE SET {updates}"
    )
    with tx() as c:
        c.execute(sql, vals)
    return get_row(table, row["id"]) or {}


def update(table: str, rid: str, fields: dict) -> dict | None:
    _connect()
    cols = [k for k in fields if k in TABLE_COLUMNS[table] and k != "id"]
    if not cols:
        return get_row(table, rid)
    with tx() as c:
        c.execute(
            f"UPDATE {table} SET {', '.join(f'{k}=?' for k in cols)} WHERE id=?",
            [_norm(fields[k]) for k in cols] + [rid],
        )
    return get_row(table, rid)


def delete(table: str, rid: str) -> None:
    with tx() as c:
        c.execute(f"DELETE FROM {table} WHERE id=?", (rid,))


def count(table: str) -> int:
    with tx() as c:
        return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def next_id(table: str, prefix: str) -> str:
    with tx() as c:
        ids = [r[0] for r in c.execute(f"SELECT id FROM {table} WHERE id LIKE ?", (prefix + "-%",))]
    n = 0
    for i in ids:
        try:
            n = max(n, int(i.split("-")[-1]))
        except ValueError:
            pass
    return f"{prefix}-{n + 1:03d}"


def clear_all() -> None:
    with tx() as c:
        for t in ("discussions", "announcements", "actions", "engagements", "opportunities"):
            c.execute(f"DELETE FROM {t}")


def get_setting(key: str, default: str | None = None) -> str | None:
    with tx() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return r[0] if r else default


def set_setting(key: str, value: str | None) -> None:
    with tx() as c:
        if value is None:
            c.execute("DELETE FROM settings WHERE key=?", (key,))
        else:
            c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def log_ai(kind: str, ref: str, prompt: str, output: str, engine: str) -> None:
    with tx() as c:
        c.execute(
            "INSERT INTO ai_log (at, kind, ref, prompt, output, engine) VALUES (?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), kind, ref, prompt[:8000], output[:8000], engine),
        )
