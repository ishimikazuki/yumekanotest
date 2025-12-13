"""長期記憶管理

重要な事実、感情的イベント、ユーザーの好みなどを保持。
ベクトル検索で関連記憶を取得する。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

from .supabase_client import get_supabase


# 記憶タイプ
MEMORY_TYPES = ["fact", "emotion", "preference", "event"]

# 減衰設定
DECAY_DAYS = 30  # 未アクセスからこの日数で減衰開始
DECAY_AMOUNT = 0.1  # 減衰量
MIN_IMPORTANCE = 0.1  # これ以下で削除対象


@dataclass
class LongTermMemoryEntry:
    """長期記憶のエントリ"""
    id: str
    user_id: str
    content: str
    memory_type: str
    importance: float
    source_mid_term_id: Optional[str]
    created_at: str
    last_accessed_at: str


class LongTermMemoryManager:
    """長期記憶管理クラス"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._supabase = get_supabase()
        self._llm_client = None

    @property
    def llm_client(self):
        """遅延初期化でLLMクライアントを取得"""
        if self._llm_client is None:
            from ..llm_client import llm_client
            self._llm_client = llm_client
        return self._llm_client

    def save(
        self,
        content: str,
        memory_type: str,
        importance: float = 0.5,
        source_mid_term_id: Optional[str] = None
    ) -> Optional[str]:
        """
        長期記憶を保存する。

        Args:
            content: 記憶内容
            memory_type: 'fact', 'emotion', 'preference', 'event'
            importance: 重要度 (0.0-1.0)
            source_mid_term_id: 元の中期記憶ID

        Returns:
            作成されたメモリのID
        """
        if memory_type not in MEMORY_TYPES:
            print(f"[LongTermMemory] 不正な記憶タイプ: {memory_type}")
            memory_type = "fact"

        # ベクトル化
        try:
            embedding = self.llm_client.embed(content)
        except Exception as e:
            print(f"[LongTermMemory] Embedding生成エラー: {e}")
            embedding = None

        try:
            data = {
                "user_id": self.user_id,
                "content": content,
                "memory_type": memory_type,
                "importance": min(1.0, max(0.0, importance)),
                "source_mid_term_id": source_mid_term_id,
            }

            if embedding:
                data["embedding"] = embedding

            result = self._supabase.table("long_term_memory").insert(data).execute()

            return result.data[0]["id"] if result.data else None
        except Exception as e:
            print(f"[LongTermMemory] 保存エラー: {e}")
            return None

    def search(self, query: str, n_results: int = 5, min_importance: float = 0.0) -> List[LongTermMemoryEntry]:
        """
        クエリに関連する記憶をベクトル検索で取得する。

        Args:
            query: 検索クエリ
            n_results: 取得件数
            min_importance: 最小重要度

        Returns:
            関連する長期記憶のリスト
        """
        try:
            # クエリをベクトル化
            query_embedding = self.llm_client.embed(query)

            # Supabaseのベクトル検索（RPC関数を使用）
            # match_long_term_memory関数はSupabaseで別途作成が必要
            result = self._supabase.client.rpc(
                "match_long_term_memory",
                {
                    "query_embedding": query_embedding,
                    "match_user_id": self.user_id,
                    "match_count": n_results,
                    "min_importance": min_importance
                }
            ).execute()

            if not result.data:
                return []

            # アクセス時間を更新
            memory_ids = [r["id"] for r in result.data]
            self._update_access_time(memory_ids)

            return [self._to_entry(r) for r in result.data]

        except Exception as e:
            print(f"[LongTermMemory] 検索エラー: {e}")
            # フォールバック: 通常の検索
            return self._fallback_search(n_results, min_importance)

    def _fallback_search(self, limit: int, min_importance: float) -> List[LongTermMemoryEntry]:
        """ベクトル検索が使えない場合のフォールバック"""
        try:
            result = self._supabase.table("long_term_memory") \
                .select("*") \
                .eq("user_id", self.user_id) \
                .gte("importance", min_importance) \
                .order("importance", desc=True) \
                .limit(limit) \
                .execute()

            return [self._to_entry(r) for r in result.data]
        except Exception as e:
            print(f"[LongTermMemory] フォールバック検索エラー: {e}")
            return []

    def get_by_type(self, memory_type: str, limit: int = 10) -> List[LongTermMemoryEntry]:
        """タイプ別に記憶を取得"""
        try:
            result = self._supabase.table("long_term_memory") \
                .select("*") \
                .eq("user_id", self.user_id) \
                .eq("memory_type", memory_type) \
                .order("importance", desc=True) \
                .limit(limit) \
                .execute()

            return [self._to_entry(r) for r in result.data]
        except Exception as e:
            print(f"[LongTermMemory] タイプ別取得エラー: {e}")
            return []

    def get_all(self, limit: int = 50) -> List[LongTermMemoryEntry]:
        """全記憶を取得"""
        try:
            result = self._supabase.table("long_term_memory") \
                .select("*") \
                .eq("user_id", self.user_id) \
                .order("importance", desc=True) \
                .limit(limit) \
                .execute()

            return [self._to_entry(r) for r in result.data]
        except Exception as e:
            print(f"[LongTermMemory] 全取得エラー: {e}")
            return []

    def update_importance(self, memory_id: str, new_importance: float) -> bool:
        """重要度を更新"""
        try:
            self._supabase.table("long_term_memory") \
                .update({"importance": min(1.0, max(0.0, new_importance))}) \
                .eq("id", memory_id) \
                .eq("user_id", self.user_id) \
                .execute()
            return True
        except Exception as e:
            print(f"[LongTermMemory] 重要度更新エラー: {e}")
            return False

    def decay_old_memories(self) -> int:
        """
        長期間アクセスされていない記憶の重要度を減衰させる。

        Returns:
            減衰させた記憶の数
        """
        threshold_date = (datetime.utcnow() - timedelta(days=DECAY_DAYS)).isoformat()

        try:
            # 古い記憶を取得
            result = self._supabase.table("long_term_memory") \
                .select("id, importance") \
                .eq("user_id", self.user_id) \
                .lt("last_accessed_at", threshold_date) \
                .execute()

            decayed_count = 0
            for memory in result.data:
                new_importance = memory["importance"] - DECAY_AMOUNT
                if new_importance < MIN_IMPORTANCE:
                    # 重要度が閾値以下なら削除
                    self.delete(memory["id"])
                else:
                    self.update_importance(memory["id"], new_importance)
                decayed_count += 1

            return decayed_count
        except Exception as e:
            print(f"[LongTermMemory] 減衰処理エラー: {e}")
            return 0

    def delete(self, memory_id: str) -> bool:
        """記憶を削除"""
        try:
            self._supabase.table("long_term_memory") \
                .delete() \
                .eq("id", memory_id) \
                .eq("user_id", self.user_id) \
                .execute()
            return True
        except Exception as e:
            print(f"[LongTermMemory] 削除エラー: {e}")
            return False

    def clear(self) -> bool:
        """ユーザーの全長期記憶をクリア"""
        try:
            self._supabase.table("long_term_memory") \
                .delete() \
                .eq("user_id", self.user_id) \
                .execute()
            return True
        except Exception as e:
            print(f"[LongTermMemory] クリアエラー: {e}")
            return False

    def _update_access_time(self, memory_ids: List[str]) -> None:
        """アクセス時間を更新"""
        try:
            for memory_id in memory_ids:
                self._supabase.table("long_term_memory") \
                    .update({"last_accessed_at": datetime.utcnow().isoformat()}) \
                    .eq("id", memory_id) \
                    .execute()
        except Exception as e:
            print(f"[LongTermMemory] アクセス時間更新エラー: {e}")

    def _to_entry(self, data: Dict) -> LongTermMemoryEntry:
        """DBレコードをLongTermMemoryEntryに変換"""
        return LongTermMemoryEntry(
            id=data["id"],
            user_id=data["user_id"],
            content=data["content"],
            memory_type=data.get("memory_type", "fact"),
            importance=data.get("importance", 0.5),
            source_mid_term_id=data.get("source_mid_term_id"),
            created_at=data.get("created_at", ""),
            last_accessed_at=data.get("last_accessed_at", "")
        )
