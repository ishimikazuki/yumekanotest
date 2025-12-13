"""階層メモリシステム統合マネージャー

短期・中期・長期記憶を統合管理する。
"""
from __future__ import annotations

from typing import Dict, List, Optional
from dataclasses import dataclass

from .short_term import ShortTermMemory, MAX_TURNS
from .mid_term import MidTermMemoryManager
from .long_term import LongTermMemoryManager


@dataclass
class RetrievedMemory:
    """取得された記憶"""
    content: str
    source: str  # 'short_term', 'mid_term', 'long_term'
    importance: float = 0.5


class HierarchicalMemory:
    """
    階層メモリシステム

    - 短期記憶: 直近の会話（最大15ターン）
    - 中期記憶: 会話の要約
    - 長期記憶: 重要な事実・感情的イベント（ベクトル検索可能）
    """

    def __init__(self, user_id: str, session_id: Optional[str] = None):
        self.user_id = user_id
        self.short_term = ShortTermMemory(user_id, session_id)
        self.mid_term = MidTermMemoryManager(user_id)
        self.long_term = LongTermMemoryManager(user_id)

    @property
    def session_id(self) -> str:
        """現在のセッションID"""
        return self.short_term.session_id

    def add_message(self, role: str, content: str) -> Dict:
        """
        メッセージを追加する。

        短期記憶に追加し、必要に応じて中期・長期記憶への昇格をトリガーする。

        Args:
            role: 'user' or 'assistant'
            content: メッセージ内容

        Returns:
            {
                "turn": 現在のターン番号,
                "promoted": 昇格が行われたかどうか,
                "summary": 昇格時の要約（あれば）
            }
        """
        turn = self.short_term.add_message(role, content)

        result = {
            "turn": turn,
            "promoted": False,
            "summary": None
        }

        # 15ターンに達したら中期記憶に昇格
        if self.short_term.should_summarize():
            promotion_result = self._promote_to_mid_term()
            if promotion_result:
                result["promoted"] = True
                result["summary"] = promotion_result.get("summary")

        return result

    def _promote_to_mid_term(self) -> Optional[Dict]:
        """短期記憶を中期記憶に昇格させる"""
        messages = self.short_term.get_all_for_summarization()
        if not messages:
            return None

        turn_start, turn_end = self.short_term.turn_range

        # 中期記憶を作成
        result = self.mid_term.create_from_short_term(
            messages=[{"role": m["role"], "content": m["content"]} for m in messages],
            session_id=self.session_id,
            turn_start=turn_start,
            turn_end=turn_end
        )

        if result:
            # 長期記憶候補があれば保存
            for candidate in result.get("long_term_candidates", []):
                self.long_term.save(
                    content=candidate["content"],
                    memory_type=candidate["memory_type"],
                    importance=candidate["importance"],
                    source_mid_term_id=result.get("mid_term_id")
                )

            # 短期記憶をクリア
            self.short_term.clear()

        return result

    def get_context(self, limit: int = MAX_TURNS) -> List[Dict[str, str]]:
        """
        現在の会話コンテキスト（短期記憶）を取得する。

        Returns:
            [{"role": "user", "content": "..."}, ...]
        """
        return self.short_term.get_messages(limit)

    def retrieve(self, query: str, n_results: int = 5) -> List[RetrievedMemory]:
        """
        クエリに関連する記憶を全階層から取得する。

        Args:
            query: 検索クエリ
            n_results: 取得件数

        Returns:
            関連する記憶のリスト（重要度順）
        """
        memories: List[RetrievedMemory] = []

        # 長期記憶からベクトル検索
        long_term_results = self.long_term.search(query, n_results=n_results)
        for entry in long_term_results:
            memories.append(RetrievedMemory(
                content=entry.content,
                source="long_term",
                importance=entry.importance
            ))

        # 中期記憶から重要な要約を取得
        mid_term_results = self.mid_term.get_important_summaries(threshold=0.5)
        for entry in mid_term_results[:3]:  # 最大3件
            memories.append(RetrievedMemory(
                content=entry.summary,
                source="mid_term",
                importance=entry.importance
            ))

        # 重要度でソートして返す
        memories.sort(key=lambda m: m.importance, reverse=True)
        return memories[:n_results]

    def get_summary_context(self) -> str:
        """
        中期・長期記憶から要約コンテキストを生成する。

        Returns:
            コンテキスト文字列
        """
        lines = []

        # 直近の中期記憶（要約）
        recent_summaries = self.mid_term.get_recent_summaries(limit=3)
        if recent_summaries:
            lines.append("【過去の会話要約】")
            for s in recent_summaries:
                lines.append(f"- {s.summary}")

        # 重要な長期記憶
        important_memories = self.long_term.get_all(limit=10)
        facts = [m for m in important_memories if m.memory_type == "fact"]
        emotions = [m for m in important_memories if m.memory_type == "emotion"]

        if facts:
            lines.append("\n【ユーザーについての事実】")
            for f in facts[:5]:
                lines.append(f"- {f.content}")

        if emotions:
            lines.append("\n【感情的に重要な出来事】")
            for e in emotions[:3]:
                lines.append(f"- {e.content}")

        return "\n".join(lines)

    def save_fact(self, content: str, importance: float = 0.7) -> Optional[str]:
        """事実を長期記憶に直接保存"""
        return self.long_term.save(content, memory_type="fact", importance=importance)

    def save_emotion(self, content: str, importance: float = 0.8) -> Optional[str]:
        """感情的イベントを長期記憶に直接保存"""
        return self.long_term.save(content, memory_type="emotion", importance=importance)

    def decay_memories(self) -> int:
        """古い記憶の重要度を減衰させる"""
        return self.long_term.decay_old_memories()

    def clear_all(self) -> None:
        """全ての記憶をクリア（注意: 取り消し不可）"""
        self.short_term.clear()
        self.mid_term.clear()
        self.long_term.clear()

    def clear_session(self) -> None:
        """現在のセッション（短期記憶）のみクリア"""
        self.short_term.clear()

    def get_stats(self) -> Dict:
        """記憶の統計情報を取得"""
        return {
            "short_term": {
                "current_turn": self.short_term.current_turn,
                "max_turns": MAX_TURNS,
                "session_id": self.session_id
            },
            "mid_term": {
                "count": len(self.mid_term.get_all())
            },
            "long_term": {
                "count": len(self.long_term.get_all())
            }
        }
