import sqlite3
import threading
import time
from typing import Optional, List, Dict, Any

DB_PATH = "./.bot.db"
_lock = threading.Lock()


def _get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    with _lock:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
        )
        cur.execute(
            """
        CREATE TABLE IF NOT EXISTS scheduled (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            run_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
        )
        """
        )
        conn.commit()
        conn.close()


def set_setting(key: str, value: str):
    with _lock:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
        conn.commit()
        conn.close()


def get_setting(key: str) -> Optional[str]:
    # Try to query; if the DB/tables aren't initialized, initialize them outside the lock and retry.
    try:
        with _lock:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cur.fetchone()
            conn.close()
            return row[0] if row else None
    except sqlite3.OperationalError:
        # Tables missing — initialize DB without holding the lock to avoid deadlock, then retry
        init_db()
        with _lock:
            conn = _get_conn()
            cur = conn.cursor()
            cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cur.fetchone()
            conn.close()
            return row[0] if row else None


def add_scheduled_post(content: str, run_at: int) -> int:
    with _lock:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO scheduled (content, run_at) VALUES (?,?)", (content, run_at))
        conn.commit()
        rowid = cur.lastrowid
        conn.close()
        return rowid


def list_scheduled() -> List[Dict[str, Any]]:
    with _lock:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, content, run_at, status FROM scheduled ORDER BY run_at")
        rows = cur.fetchall()
        conn.close()
        return [
            {"id": r[0], "content": r[1], "run_at": r[2], "status": r[3]} for r in rows
        ]


def mark_scheduled_sent(post_id: int):
    with _lock:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE scheduled SET status = 'sent' WHERE id = ?", (post_id,))
        conn.commit()
        conn.close()
