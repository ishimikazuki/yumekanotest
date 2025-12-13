"""ルールセレクター - 当該ターンに適用されるルールを抽出・要約"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, TYPE_CHECKING

from .rule_registry import RuleRegistry
from .rule_types import HardRule, SoftRule, StateDependentRule

if TYPE_CHECKING:
    from ..models import UserState


@dataclass
class SelectedRules:
    """当該ターンに適用されるルールセット"""
    hard_rules: List[HardRule]
    soft_rules: List[SoftRule]
    state_dependent_rules: List[StateDependentRule]
    allow_nsfw: bool
    summary: str  # LLMに渡す要約テキスト


class RuleSelector:
    """当該ターンに適用されるルールを抽出し、要約を生成"""

    def __init__(self, registry: Optional[RuleRegistry] = None):
        self._registry = registry or RuleRegistry.get_instance()

    def select_rules(
        self,
        state: "UserState",
        user_message: str,
        history: List[Dict],
    ) -> SelectedRules:
        """現在の状態に基づいて適用ルールを選択"""

        # HardRulesは常に全て適用
        hard_rules = self._registry.get_hard_rules()

        # SoftRulesは条件があれば評価
        soft_rules = []
        for rule in self._registry.get_soft_rules():
            if rule.condition:
                if self._evaluate_condition(rule.condition, state, user_message):
                    soft_rules.append(rule)
            else:
                soft_rules.append(rule)

        # StateDependentRulesは条件評価
        applicable_sdr = []
        allow_nsfw = False

        for rule in self._registry.get_state_dependent_rules():
            if self._evaluate_condition(rule.condition, state, user_message):
                applicable_sdr.append(rule)
                if rule.allow_nsfw:
                    allow_nsfw = True

        # 要約生成
        summary = self._generate_summary(hard_rules, soft_rules, applicable_sdr, allow_nsfw, state)

        return SelectedRules(
            hard_rules=hard_rules,
            soft_rules=soft_rules,
            state_dependent_rules=applicable_sdr,
            allow_nsfw=allow_nsfw,
            summary=summary,
        )

    def _evaluate_condition(
        self,
        condition: Dict[str, Any],
        state: "UserState",
        user_message: str,
    ) -> bool:
        """MongoDB-like条件式を評価"""
        if not condition:
            return True

        for key, value in condition.items():
            # シーン条件
            if key == "current_scene":
                if state.scenario.current_scene != value:
                    return False

            # フェーズ条件
            elif key == "current_phase":
                if isinstance(value, dict) and "$in" in value:
                    if state.scenario.current_phase not in value["$in"]:
                        return False
                elif state.scenario.current_phase != value:
                    return False

            # ターンカウント条件
            elif key == "turn_count_in_phase":
                actual = state.scenario.turn_count_in_phase
                if isinstance(value, dict):
                    if "$lte" in value and actual > value["$lte"]:
                        return False
                    if "$gte" in value and actual < value["$gte"]:
                        return False
                    if "$lt" in value and actual >= value["$lt"]:
                        return False
                    if "$gt" in value and actual <= value["$gt"]:
                        return False
                    if "$eq" in value and actual != value["$eq"]:
                        return False
                elif actual != value:
                    return False

            # 感情条件 (arousal)
            elif key == "arousal":
                actual = state.emotion.arousal
                if isinstance(value, dict):
                    if "$gte" in value and actual < value["$gte"]:
                        return False
                    if "$lte" in value and actual > value["$lte"]:
                        return False
                elif actual != value:
                    return False

            # 感情条件 (pleasure)
            elif key == "pleasure":
                actual = state.emotion.pleasure
                if isinstance(value, dict):
                    if "$gte" in value and actual < value["$gte"]:
                        return False
                    if "$lte" in value and actual > value["$lte"]:
                        return False
                elif actual != value:
                    return False

            # 感情条件 (dominance)
            elif key == "dominance":
                actual = state.emotion.dominance
                if isinstance(value, dict):
                    if "$gte" in value and actual < value["$gte"]:
                        return False
                    if "$lte" in value and actual > value["$lte"]:
                        return False
                elif actual != value:
                    return False

            # コンテキストキーワード条件
            elif key == "context_keywords":
                if isinstance(value, list):
                    if not any(kw in user_message for kw in value):
                        return False

            # 感情ラベル条件
            elif key == "emotion":
                # 簡易実装: user_messageに特定のキーワードがあるか
                if value == "scolded":
                    scolded_keywords = ["怒", "うるさい", "黙れ", "バカ", "アホ"]
                    if not any(kw in user_message for kw in scolded_keywords):
                        return False

            # 変数条件
            elif key == "variables":
                if isinstance(value, dict):
                    for var_key, var_value in value.items():
                        if state.scenario.variables.get(var_key) != var_value:
                            return False

        return True

    def _generate_summary(
        self,
        hard_rules: List[HardRule],
        soft_rules: List[SoftRule],
        state_dependent: List[StateDependentRule],
        allow_nsfw: bool,
        state: "UserState",
    ) -> str:
        """ルール要約をテキストで生成（LLMプロンプト用）"""
        lines = ["## 適用ルール要約"]

        # 現在の状態
        lines.append(f"\n### 現在の状態")
        lines.append(f"- フェーズ: {state.scenario.current_phase}")
        lines.append(f"- シーン: {state.scenario.current_scene}")
        lines.append(f"- ターン: {state.scenario.turn_count_in_phase}")
        lines.append(f"- 感情(PAD): P={state.emotion.pleasure:.1f}, A={state.emotion.arousal:.1f}, D={state.emotion.dominance:.1f}")

        # 必須ルール
        lines.append("\n### 必須ルール（違反不可）")
        for rule in hard_rules[:5]:  # 上位5件のみ表示
            lines.append(f"- {rule.description}")
        if len(hard_rules) > 5:
            lines.append(f"- ...他 {len(hard_rules) - 5} 件")

        # 推奨ルール
        if soft_rules:
            lines.append("\n### 推奨ルール")
            for rule in soft_rules[:3]:
                lines.append(f"- {rule.description}")
            if len(soft_rules) > 3:
                lines.append(f"- ...他 {len(soft_rules) - 3} 件")

        # 状態依存ルール
        if state_dependent:
            lines.append("\n### 状態依存ルール（現在適用中）")
            for rule in state_dependent:
                lines.append(f"- {rule.description}")
                if rule.prompt_hint:
                    lines.append(f"  → {rule.prompt_hint}")

        # NSFW許可
        if allow_nsfw:
            lines.append("\n### NSFW許可: あり（フェーズ進行により解禁）")
        else:
            lines.append("\n### NSFW許可: なし")

        return "\n".join(lines)

    def get_rules_for_validation(
        self,
        state: "UserState",
        user_message: str,
        history: List[Dict],
    ) -> SelectedRules:
        """検証用にルールを取得（select_rulesのエイリアス）"""
        return self.select_rules(state, user_message, history)
