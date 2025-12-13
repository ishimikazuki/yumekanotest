"""短期記憶管理

直近の会話（最大15ターン）を保持する。
15ターンを超えると中期記憶への昇格処理をトリガーする。
"""
from __future__ import annotations

import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass

from .supabase_client import get_supabase


MAX_TURNS = 15  # 短期記憶の最大ターン数


@dataclass
class ShortTermMessage:
    """短期記憶のメッセージ"""
    id: str
    user_id: str
    role: str
    content: str
    turn_number: int
    session_id: str
    created_at: str


class ShortTermMemory:
    """短期記憶管理クラス"""

    def __init__(self, user_id: str, session_id: Optional[str] = None):
        self.user_id = user_id
        self.session_id = session_id or str(uuid.uuid4())
        self._supabase = get_supabase()
        self._current_turn = 0
        self._load_current_turn()

    def _load_current_turn(self):
        """現在のターン番号をDBから取得"""
        try:
            result = self._supabase.table("short_term_memory") \
                .select("turn_number") \
                .eq("user_id", self.user_id) \
                .eq("session_id", self.session_id) \
                .order("turn_number", desc=True) \
                .limit(1) \
                .execute()

            if result.data:
                self._current_turn = result.data[0]["turn_number"]
        except Exception as e:
            print(f"[ShortTermMemory] ターン取得エラー: {e}")
            self._current_turn = 0

    def add_message(self, role: str, content: str) -> int:
        """
        メッセージを追加する。

        Returns:
            現在のターン番号
        """
        # userメッセージでターン番号を増やす
        if role == "user":
            self._current_turn += 1

        try:
            self._supabase.table("short_term_memory").insert({
                "user_id": self.user_id,
                "role": role,
                "content": content,
                "turn_number": self._current_turn,
                "session_id": self.session_id,
            }).execute()
        except Exception as e:
            print(f"[ShortTermMemory] 保存エラー: {e}")

        return self._current_turn

    def get_messages(self, limit: int = MAX_TURNS) -> List[Dict[str, str]]:
        """
        直近のメッセージを取得する。

        Returns:
            [{"role": "user", "content": "..."}, ...]
        """
        try:
            result = self._supabase.table("short_term_memory") \
                .select("role, content, turn_number") \
                .eq("user_id", self.user_id) \
                .eq("session_id", self.session_id) \
                .order("turn_number", desc=False) \
                .order("created_at", desc=False) \
                .limit(limit * 2) \
                .execute()

            return [{"role": r["role"], "content": r["content"]} for r in result.data]
        except Exception as e:
            print(f"[ShortTermMemory] 取得エラー: {e}")
            return []

    def get_all_for_summarization(self) -> List[Dict]:
        """要約用に全メッセージを取得"""
        try:
            result = self._supabase.table("short_term_memory") \
                .select("*") \
                .eq("user_id", self.user_id) \
                .eq("session_id", self.session_id) \
                .order("turn_number", desc=False) \
                .order("created_at", desc=False) \
                .execute()

            return result.data
        except Exception as e:
            print(f"[ShortTermMemory] 取得エラー: {e}")
            return []

    def clear(self):
        """セッションの短期記憶をクリア"""
        try:
            self._supabase.table("short_term_memory") \
                .delete() \
                .eq("user_id", self.user_id) \
                .eq("session_id", self.session_id) \
                .execute()
            self._current_turn = 0
        except Exception as e:
            print(f"[ShortTermMemory] クリアエラー: {e}")

    def should_summarize(self) -> bool:
        """中期記憶への昇格が必要か判定"""
        return self._current_turn >= MAX_TURNS

    @property
    def current_turn(self) -> int:
        return self._current_turn

    @property
    def turn_range(self) -> tuple:
        """現在のターン範囲を返す"""
        return (1, self._current_turn)
