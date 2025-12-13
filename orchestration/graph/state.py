"""LangGraph用の状態定義"""
from typing import TypedDict, List, Optional, Dict, Any

from ..models import UserState
from ..rules.rule_selector import SelectedRules
from ..validation.output_validator import ValidationResult


class GraphState(TypedDict):
    """対話グラフの状態"""
    # 入力
    user_id: str
    user_message: str

    # ゲーム状態
    user_state: Optional[UserState]
    history: List[Dict[str, str]]
    memories: List[str]

    # ルール
    selected_rules: Optional[SelectedRules]

    # 生成
    draft_reply: str
    final_reply: str

    # 検証
    validation_result: Optional[ValidationResult]
    retry_count: int
    max_retries: int

    # Observer からの指示
    instruction_override: Optional[str]

    # エラー情報
    errors: List[str]
