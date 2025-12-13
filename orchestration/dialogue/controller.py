"""DialogueController: 1ターンの対話制御"""
from __future__ import annotations
from typing import Dict, Any, Optional
import os

from ..models import UserState


class DialogueController:
    """
    対話コントローラー
    LangGraph または既存のorchestratorを使って1ターンの対話を処理する。
    """

    def __init__(self, use_langgraph: Optional[bool] = None):
        """
        Args:
            use_langgraph: LangGraphを使用するかどうか。
                           Noneの場合は環境変数 USE_LANGGRAPH を参照。
        """
        if use_langgraph is None:
            use_langgraph = os.getenv("USE_LANGGRAPH", "false").lower() == "true"
        self._use_langgraph = use_langgraph

    def process_turn(self, user_id: str, user_message: str) -> Dict[str, Any]:
        """
        1ターンの対話を処理する。

        Args:
            user_id: ユーザーID
            user_message: ユーザーの入力メッセージ

        Returns:
            Dict: {"reply": str, "state": UserState}
        """
        if self._use_langgraph:
            return self._process_with_langgraph(user_id, user_message)
        else:
            return self._process_with_legacy(user_id, user_message)

    def _process_with_langgraph(self, user_id: str, user_message: str) -> Dict[str, Any]:
        """LangGraphを使った処理"""
        from ..graph.dialogue_graph import run_dialogue_graph
        return run_dialogue_graph(user_id, user_message)

    def _process_with_legacy(self, user_id: str, user_message: str) -> Dict[str, Any]:
        """既存のorchestratorを使った処理"""
        from ..orchestrator import process_chat_turn
        return process_chat_turn(user_id, user_message)

    def reset_session(self, user_id: str) -> None:
        """セッションをリセットする"""
        from ..orchestrator import reset_session
        reset_session(user_id)
