"""メモリ圧縮・メンテナンス

週次要約、スコア減衰、アーカイブ処理を行う。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .supabase_client import get_supabase


# 設定
DECAY_DAYS = 30  # 未アクセスからこの日数で減衰開始
DECAY_AMOUNT = 0.1  # 減衰量
MIN_IMPORTANCE = 0.1  # これ以下でアーカイブ対象
WEEKLY_SUMMARY_DAYS = 7  # 週次要約の対象日数


class MemoryCompressor:
    """
    メモリ圧縮・メンテナンスクラス

    定期的なメモリメンテナンスを実行する:
    - 週次要約: 中期記憶を週単位で要約
    - スコア減衰: 古いエピソードの重要度を減衰
    - アーカイブ: 重要度が閾値以下のエピソードをアーカイブ
    """

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

    def create_weekly_summary(self) -> Optional[str]:
        """
        今週の中期記憶を要約する。

        Returns:
            要約テキスト（記憶がない場合はNone）
        """
        try:
            # 今週の中期記憶を取得
            week_ago = (datetime.utcnow() - timedelta(days=WEEKLY_SUMMARY_DAYS)).isoformat()

            result = self._supabase.table("mid_term_memory") \
                .select("id, summary, importance, created_at") \
                .eq("user_id", self.user_id) \
                .gte("created_at", week_ago) \
                .order("created_at", desc=False) \
                .execute()

            memories = result.data
            if not memories:
                return None

            # LLMで要約を生成
            summaries_text = "\n".join([
                f"- {m['summary']} (重要度: {m['importance']:.1f})"
                for m in memories
            ])

            prompt = f"""以下の今週の会話要約を1つの週次要約にまとめてください。

## 今週の会話要約
{summaries_text}

## 出力形式（JSON）
{{
    "summary": "今週の出来事を2-3文で要約"
}}
"""

            llm_result = self.llm_client.json_chat(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="あなたは会話要約の専門家です。"
            )

            weekly_summary = llm_result.get("summary", "")

            if weekly_summary:
                # DBに保存
                self._supabase.table("weekly_summaries").insert({
                    "user_id": self.user_id,
                    "summary": weekly_summary,
                    "week_start": week_ago,
                    "week_end": datetime.utcnow().isoformat(),
                    "source_mid_term_ids": [m["id"] for m in memories],
                }).execute()

            return weekly_summary

        except Exception as e:
            print(f"[MemoryCompressor] 週次要約エラー: {e}")
            return None

    def decay_memories(self) -> int:
        """
        古い記憶の重要度を減衰させる。

        Returns:
            減衰させた記憶の数
        """
        try:
            threshold_date = (datetime.utcnow() - timedelta(days=DECAY_DAYS)).isoformat()

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
                    self._supabase.table("long_term_memory") \
                        .delete() \
                        .eq("id", memory["id"]) \
                        .execute()
                else:
                    # 重要度を更新
                    self._supabase.table("long_term_memory") \
                        .update({"importance": new_importance}) \
                        .eq("id", memory["id"]) \
                        .execute()

                decayed_count += 1

            return decayed_count

        except Exception as e:
            print(f"[MemoryCompressor] 減衰処理エラー: {e}")
            return 0

    def archive_low_importance(self, threshold: float = MIN_IMPORTANCE) -> int:
        """
        低重要度の記憶をアーカイブする。

        Args:
            threshold: アーカイブ閾値（デフォルト: 0.1）

        Returns:
            アーカイブした記憶の数
        """
        try:
            # 低重要度の記憶を取得
            result = self._supabase.table("long_term_memory") \
                .select("*") \
                .eq("user_id", self.user_id) \
                .lt("importance", threshold) \
                .execute()

            archived_count = 0
            for memory in result.data:
                # アーカイブテーブルに移動
                archive_data = {
                    "original_id": memory["id"],
                    "user_id": memory["user_id"],
                    "content": memory["content"],
                    "memory_type": memory.get("memory_type", "fact"),
                    "importance": memory["importance"],
                    "original_created_at": memory.get("created_at"),
                    "archived_at": datetime.utcnow().isoformat(),
                }
                self._supabase.table("archived_memories").insert(archive_data).execute()

                # 元テーブルから削除
                self._supabase.table("long_term_memory") \
                    .delete() \
                    .eq("id", memory["id"]) \
                    .execute()

                archived_count += 1

            return archived_count

        except Exception as e:
            print(f"[MemoryCompressor] アーカイブエラー: {e}")
            return 0

    def run_maintenance(self) -> Dict:
        """
        定期メンテナンスを一括実行する。

        Returns:
            {
                "weekly_summary": 週次要約（なければNone）,
                "decayed_count": 減衰した記憶数,
                "archived_count": アーカイブした記憶数,
                "executed_at": 実行日時
            }
        """
        result = {
            "weekly_summary": None,
            "decayed_count": 0,
            "archived_count": 0,
            "executed_at": datetime.utcnow().isoformat(),
        }

        # 1. 週次要約
        result["weekly_summary"] = self.create_weekly_summary()

        # 2. スコア減衰
        result["decayed_count"] = self.decay_memories()

        # 3. アーカイブ
        result["archived_count"] = self.archive_low_importance()

        print(f"[MemoryCompressor] メンテナンス完了: {result}")
        return result
