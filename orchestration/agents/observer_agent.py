"""ObserverAgent: 既存observer.pyのクラスラッパー"""
from __future__ import annotations
from typing import List, Dict, Optional

from ..models import UserState, ObservationResult
from ..observer import update_state as _update_state


class ObserverAgent:
    """
    Observer エージェント
    ユーザーメッセージからゲーム状態（感情・シナリオ）を更新する。
    既存の observer.py をラップし、クラスベースのインターフェースを提供。
    """

    def __init__(self):
        pass

    def update_state(
        self,
        user_message: str,
        current_state: UserState,
        history: List[Dict],
    ) -> ObservationResult:
        """
        ユーザーメッセージに基づいて状態を更新する。

        Args:
            user_message: ユーザーの入力メッセージ
            current_state: 現在のユーザー状態
            history: 会話履歴

        Returns:
            ObservationResult: 更新された状態と、必要に応じてActorへの指示
        """
        return _update_state(user_message, current_state, history)

    def observe(
        self,
        user_message: str,
        state: UserState,
        history: List[Dict],
    ) -> ObservationResult:
        """update_stateのエイリアス"""
        return self.update_state(user_message, state, history)
