"""SQLite storage: conversation history, notes, reminders and settings."""
import sqlite3
import threading
import time
from contextlib import contextmanager

import config

_lock = threading.Lock()


@contextmanager
def _db():
    with _lock:
        conn = sqlite3.connect(config.DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


def init() -> None:
    config.ensure_dirs()
    with _db() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, ts REAL, role TEXT, text TEXT);
            CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, ts REAL, title TEXT, body TEXT);
            CREATE TABLE IF NOT EXISTS reminders(id INTEGER PRIMARY KEY, due REAL, text TEXT, done INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
            """
        )


# --- conversation -----------------------------------------------------------
def save_message(role: str, text: str) -> None:
    if not config.SAVE_HISTORY:
        return
    with _db() as c:
        c.execute("INSERT INTO messages(ts, role, text) VALUES (?,?,?)", (time.time(), role, text))


def recent_messages(limit: int = 20):
    with _db() as c:
        rows = c.execute("SELECT role, text FROM messages ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in reversed(rows)]


def preload_history(limit: int = 8):
    """Recent turns shaped for the model: starts with a user turn and strictly alternates."""
    out, expect = [], "user"
    for m in recent_messages(limit):
        if m["role"] == expect:
            out.append(m)
            expect = "jarvis" if expect == "user" else "user"
    if out and out[-1]["role"] == "user":
        out.pop()
    return out


def clear_history() -> None:
    with _db() as c:
        c.execute("DELETE FROM messages")


# --- notes ------------------------------------------------------------------
def add_note(title: str, body: str) -> int:
    with _db() as c:
        return c.execute("INSERT INTO notes(ts, title, body) VALUES (?,?,?)", (time.time(), title, body)).lastrowid


def list_notes(limit: int = 10):
    with _db() as c:
        rows = c.execute("SELECT id, ts, title, body FROM notes ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# --- reminders --------------------------------------------------------------
def add_reminder(text: str, due_ts: float) -> int:
    with _db() as c:
        return c.execute("INSERT INTO reminders(due, text) VALUES (?,?)", (due_ts, text)).lastrowid


def due_reminders():
    with _db() as c:
        rows = c.execute("SELECT id, text FROM reminders WHERE done=0 AND due<=?", (time.time(),)).fetchall()
        c.executemany("UPDATE reminders SET done=1 WHERE id=?", [(r["id"],) for r in rows])
    return [dict(r) for r in rows]


# --- settings ---------------------------------------------------------------
def get_setting(key: str, default=None):
    with _db() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _db() as c:
        c.execute("INSERT INTO settings(key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
