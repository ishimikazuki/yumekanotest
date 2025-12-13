"""GameStateGateway: ゲームコアとの橋渡し"""
from __future__ import annotations
from typing import Dict, List, Optional

from ..models import UserState
from ..storage import (
    init_db,
    fetch_state,
    update_state,
    fetch_history,
    append_log,
    reset_user,
)


class GameStateGateway:
    """
    ゲーム状態ゲートウェイ
    既存のストレージ層（SQLite）へのファサード。
    """

    def __init__(self):
        self._initialized = False

    def ensure_initialized(self) -> None:
        """DB初期化を確実に行う"""
        if not self._initialized:
            init_db()
            self._initialized = True

    def fetch_state(self, user_id: str) -> Optional[UserState]:
        """
        ユーザーの現在状態を取得する。

        Args:
            user_id: ユーザーID

        Returns:
            UserState or None: ユーザー状態（存在しない場合はNone）
        """
        self.ensure_initialized()
        return fetch_state(user_id)

    def update_state(self, user_id: str, state: UserState) -> None:
        """
        ユーザーの状態を保存する。

        Args:
            user_id: ユーザーID
            state: 保存する状態
        """
        self.ensure_initialized()
        update_state(user_id, state)

    def fetch_history(self, user_id: str, limit: int = 20) -> List[Dict]:
        """
        会話履歴を取得する。

        Args:
            user_id: ユーザーID
            limit: 取得件数

        Returns:
            List[Dict]: 会話履歴
        """
        self.ensure_initialized()
        return fetch_history(user_id, limit)

    def append_log(self, user_id: str, role: str, content: str) -> None:
        """
        会話ログを追加する。

        Args:
            user_id: ユーザーID
            role: ロール（"user" or "assistant"）
            content: メッセージ内容
        """
        self.ensure_initialized()
        append_log(user_id, role, content)

    def reset_user(self, user_id: str) -> None:
        """
        ユーザーデータをリセットする。

        Args:
            user_id: ユーザーID
        """
        self.ensure_initialized()
        reset_user(user_id)

    def get_or_create_state(self, user_id: str) -> UserState:
        """
        ユーザー状態を取得し、なければ新規作成する。

        Args:
            user_id: ユーザーID

        Returns:
            UserState: ユーザー状態
        """
        state = self.fetch_state(user_id)
        if state is None:
            state = UserState.new(user_id)
        return state
