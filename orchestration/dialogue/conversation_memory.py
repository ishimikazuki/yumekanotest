"""ConversationMemory: 会話ログの管理"""
from __future__ import annotations
from typing import List, Dict, Optional

from ..memory import memory_system, MemoryItem


class ConversationMemory:
    """
    会話メモリ
    ChromaDBベースの長期記憶を管理する。
    """

    def __init__(self):
        self._memory_system = memory_system

    def save(
        self,
        user_id: str,
        user_message: str,
        assistant_reply: str,
        phase: str,
    ) -> None:
        """
        会話を長期記憶に保存する。

        Args:
            user_id: ユーザーID
            user_message: ユーザーの入力
            assistant_reply: アシスタントの返答
            phase: 現在のフェーズ
        """
        # ユーザーメッセージを保存
        self._memory_system.save_memory(
            user_id,
            f"User: {user_message}",
            role="user",
            phase=phase,
        )

        # アシスタントの返答を保存
        self._memory_system.save_memory(
            user_id,
            f"Me(Seira): {assistant_reply}",
            role="assistant",
            phase=phase,
        )

    def retrieve(
        self,
        user_id: str,
        query: str,
        n_results: int = 3,
    ) -> List[str]:
        """
        関連する記憶を検索する。

        Args:
            user_id: ユーザーID
            query: 検索クエリ
            n_results: 取得件数

        Returns:
            List[str]: 関連記憶のテキストリスト
        """
        memories = self._memory_system.retrieve_memory(user_id, query, n_results)
        return [m.text for m in memories]

    def retrieve_with_metadata(
        self,
        user_id: str,
        query: str,
        n_results: int = 3,
    ) -> List[MemoryItem]:
        """
        メタデータ付きで関連記憶を検索する。

        Args:
            user_id: ユーザーID
            query: 検索クエリ
            n_results: 取得件数

        Returns:
            List[MemoryItem]: 関連記憶のリスト
        """
        return self._memory_system.retrieve_memory(user_id, query, n_results)

    def clear(self, user_id: str) -> None:
        """
        ユーザーの記憶をクリアする。

        Args:
            user_id: ユーザーID
        """
        self._memory_system.clear_memory(user_id)
