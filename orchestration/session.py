"""セッション管理。

チャット履歴はメモリ内に保持し、DBには保存しない。
長期記憶のみChromaDBに保存する。
"""
from __future__ import annotations

from typing import Dict, List
from dataclasses import dataclass, field
import threading


@dataclass
class Session:
    """1ユーザーのセッション"""
    user_id: str
    history: List[Dict[str, str]] = field(default_factory=list)

    def add_message(self, role: str, content: str):
        """履歴にメッセージを追加"""
        self.history.append({"role": role, "content": content})

    def get_history(self, limit: int = 20) -> List[Dict[str, str]]:
        """直近の履歴を取得"""
        return self.history[-limit:]

    def clear(self):
        """履歴をクリア"""
        self.history.clear()


class SessionManager:
    """セッション管理（シングルトン）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._sessions: Dict[str, Session] = {}

    def get_session(self, user_id: str) -> Session:
        """セッションを取得（なければ作成）"""
        if user_id not in self._sessions:
            self._sessions[user_id] = Session(user_id=user_id)
        return self._sessions[user_id]

    def clear_session(self, user_id: str):
        """セッションをクリア"""
        if user_id in self._sessions:
            self._sessions[user_id].clear()

    def delete_session(self, user_id: str):
        """セッションを削除"""
        self._sessions.pop(user_id, None)


# グローバルインスタンス
session_manager = SessionManager()
