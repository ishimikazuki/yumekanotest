"""ActorModel: 既存actor.pyのクラスラッパー"""
from __future__ import annotations
from typing import List, Dict, Optional

from ..models import UserState, EmotionState
from ..actor import generate_reply as _generate_reply


class ActorModel:
    """
    Actor モデル
    キャラクター（蒼井セイラ）として発話を生成する。
    既存の actor.py をラップし、クラスベースのインターフェースを提供。
    """

    def __init__(self):
        pass

    def generate(
        self,
        user_message: str,
        history: List[Dict],
        state: UserState,
        memories: List[str],
        rules_summary: Optional[str] = None,
        instruction_override: Optional[str] = None,
    ) -> str:
        """
        発話を生成する。

        Args:
            user_message: ユーザーの入力メッセージ
            history: 会話履歴
            state: 現在のユーザー状態
            memories: 関連する長期記憶
            rules_summary: 適用ルールの要約（オプション）
            instruction_override: Observerからの強制指示

        Returns:
            str: 生成された発話
        """
        # ルール要約を instruction に追加
        combined_instruction = instruction_override or ""
        if rules_summary:
            combined_instruction += f"\n\n{rules_summary}"

        return _generate_reply(
            user_message=user_message,
            history=history,
            state=state,
            relevant_memories=memories,
            instruction_override=combined_instruction if combined_instruction else None,
        )

    def generate_reply(
        self,
        user_message: str,
        history: List[Dict],
        state: UserState,
        relevant_memories: List[str],
        instruction_override: Optional[str] = None,
    ) -> str:
        """generate のエイリアス（後方互換性用）"""
        return self.generate(
            user_message=user_message,
            history=history,
            state=state,
            memories=relevant_memories,
            instruction_override=instruction_override,
        )

    @staticmethod
    def tone_from_emotion(emo: EmotionState) -> str:
        """PADモデルに基づく演技指針を生成"""
        tone = []
        if emo.pleasure >= 5.0:
            tone.append("明るく楽しげに")
        elif emo.pleasure <= -5.0:
            tone.append("不機嫌に、冷たく")

        if emo.arousal >= 5.0:
            tone.append("テンション高く")
        elif emo.arousal <= -5.0:
            tone.append("落ち着いて、あるいは眠げに")

        if emo.dominance >= 5.0:
            tone.append("自信満々に")
        elif emo.dominance <= -5.0:
            tone.append("控えめに、おどおどと")

        return "、".join(tone) if tone else "自然体で"
