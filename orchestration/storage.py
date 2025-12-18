"""SQLite を用いたシンプルなステート永続化層。"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional

from .models import UserState, utc_now

# Vercel環境では/tmpを使用（サーバーレスの一時ストレージ）
IS_VERCEL = os.getenv("VERCEL") == "1"
if IS_VERCEL:
    DB_PATH = Path("/tmp/data/bot.db")
else:
    DB_PATH = Path("data/bot.db")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_states (
                user_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.commit()


def fetch_state(user_id: str) -> Optional[UserState]:
    with _connect() as conn:
        cur = conn.execute(
            "SELECT state_json FROM user_states WHERE user_id = ?", (user_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        data = json.loads(row["state_json"])
        return UserState.from_dict(data)


def update_state(user_id: str, state: UserState) -> None:
    state.updated_at = utc_now()
    payload = json.dumps(state.to_dict(), ensure_ascii=False)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO user_states (user_id, state_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                state_json=excluded.state_json,
                updated_at=excluded.updated_at
            """,
            (user_id, payload, state.updated_at),
        )
        conn.commit()


def fetch_history(user_id: str, limit: int = 10) -> List[Dict]:
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT role, content, created_at
              FROM chat_logs
             WHERE user_id = ?
             ORDER BY id DESC
             LIMIT ?
            """,
            (user_id, limit),
        )
        rows = cur.fetchall()
    # 逆順で返す（古い順）
    history = [{"role": r["role"], "content": r["content"], "created_at": r["created_at"]} for r in reversed(rows)]
    return history


def append_log(user_id: str, role: str, content: str) -> None:
    now = utc_now()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO chat_logs (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (user_id, role, content, now),
        )
        conn.commit()


def reset_user(user_id: str) -> None:
    """指定ユーザーの状態と履歴を削除（デバッグ用）。"""
    with _connect() as conn:
        conn.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM chat_logs WHERE user_id = ?", (user_id,))
        conn.commit()
def reset_user(user_id: str) -> None:
    """ユーザーの状態とログを完全に削除する。"""
    with _connect() as conn:
        conn.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM chat_logs WHERE user_id = ?", (user_id,))
        conn.commit()
