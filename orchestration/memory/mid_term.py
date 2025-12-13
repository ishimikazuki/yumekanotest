"""中期記憶管理

短期記憶の要約を保持し、重要度が高いものは長期記憶に昇格させる。
"""
from __future__ import annotations

import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass

from .supabase_client import get_supabase
from .summarizer import summarize_conversation, extract_long_term_memories


PROMOTION_THRESHOLD = 0.7  # 長期記憶への昇格閾値


@dataclass
class MidTermMemory:
    """中期記憶のエントリ"""
    id: str
    user_id: str
    summary: str
    importance: float
    source_session_id: str
    turn_start: int
    turn_end: int
    created_at: str


class MidTermMemoryManager:
    """中期記憶管理クラス"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._supabase = get_supabase()

    def create_from_short_term(
        self,
        messages: List[Dict],
        session_id: str,
        turn_start: int,
        turn_end: int
    ) -> Optional[Dict]:
        """
        短期記憶から中期記憶を作成する。

        Args:
            messages: 短期記憶のメッセージリスト
            session_id: セッションID
            turn_start: 開始ターン番号
            turn_end: 終了ターン番号

        Returns:
            作成された中期記憶のID、要約結果、長期記憶候補を含む辞書
        """
        if not messages:
            return None

        # 会話を要約
        summary_result = summarize_conversation(messages)

        if not summary_result.get("summary"):
            print("[MidTermMemory] 要約が空のためスキップ")
            return None

        # 中期記憶に保存
        try:
            result = self._supabase.table("mid_term_memory").insert({
                "user_id": self.user_id,
                "summary": summary_result["summary"],
                "importance": summary_result["importance"],
                "source_session_id": session_id,
                "turn_range": f"[{turn_start},{turn_end}]",
            }).execute()

            mid_term_id = result.data[0]["id"] if result.data else None

            # 長期記憶に昇格すべき項目を抽出
            long_term_candidates = []
            if summary_result["importance"] >= PROMOTION_THRESHOLD:
                long_term_candidates = extract_long_term_memories(summary_result)

            return {
                "mid_term_id": mid_term_id,
                "summary": summary_result["summary"],
                "importance": summary_result["importance"],
                "long_term_candidates": long_term_candidates
            }

        except Exception as e:
            print(f"[MidTermMemory] 保存エラー: {e}")
            return None

    def get_recent_summaries(self, limit: int = 5) -> List[MidTermMemory]:
        """直近の要約を取得"""
        try:
            result = self._supabase.table("mid_term_memory") \
                .select("*") \
                .eq("user_id", self.user_id) \
                .order("created_at", desc=True) \
                .limit(limit) \
                .execute()

            return [self._to_memory(r) for r in result.data]
        except Exception as e:
            print(f"[MidTermMemory] 取得エラー: {e}")
            return []

    def get_important_summaries(self, threshold: float = 0.5) -> List[MidTermMemory]:
        """重要度が閾値以上の要約を取得"""
        try:
            result = self._supabase.table("mid_term_memory") \
                .select("*") \
                .eq("user_id", self.user_id) \
                .gte("importance", threshold) \
                .order("importance", desc=True) \
                .execute()

            return [self._to_memory(r) for r in result.data]
        except Exception as e:
            print(f"[MidTermMemory] 取得エラー: {e}")
            return []

    def get_all(self) -> List[MidTermMemory]:
        """全ての中期記憶を取得"""
        try:
            result = self._supabase.table("mid_term_memory") \
                .select("*") \
                .eq("user_id", self.user_id) \
                .order("created_at", desc=True) \
                .execute()

            return [self._to_memory(r) for r in result.data]
        except Exception as e:
            print(f"[MidTermMemory] 取得エラー: {e}")
            return []

    def delete(self, memory_id: str) -> bool:
        """中期記憶を削除"""
        try:
            self._supabase.table("mid_term_memory") \
                .delete() \
                .eq("id", memory_id) \
                .eq("user_id", self.user_id) \
                .execute()
            return True
        except Exception as e:
            print(f"[MidTermMemory] 削除エラー: {e}")
            return False

    def clear(self) -> bool:
        """ユーザーの全中期記憶をクリア"""
        try:
            self._supabase.table("mid_term_memory") \
                .delete() \
                .eq("user_id", self.user_id) \
                .execute()
            return True
        except Exception as e:
            print(f"[MidTermMemory] クリアエラー: {e}")
            return False

    def _to_memory(self, data: Dict) -> MidTermMemory:
        """DBレコードをMidTermMemoryに変換"""
        # turn_rangeをパース: "[1,15]" -> (1, 15)
        turn_range = data.get("turn_range", "[0,0]")
        if isinstance(turn_range, str):
            # "[1,15]" -> "1,15" -> ["1", "15"]
            turn_range = turn_range.strip("[]").split(",")
            turn_start = int(turn_range[0]) if len(turn_range) > 0 else 0
            turn_end = int(turn_range[1]) if len(turn_range) > 1 else 0
        else:
            turn_start, turn_end = 0, 0

        return MidTermMemory(
            id=data["id"],
            user_id=data["user_id"],
            summary=data["summary"],
            importance=data.get("importance", 0.5),
            source_session_id=data.get("source_session_id", ""),
            turn_start=turn_start,
            turn_end=turn_end,
            created_at=data.get("created_at", "")
        )
