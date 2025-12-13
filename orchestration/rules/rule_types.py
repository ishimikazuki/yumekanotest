"""ルールの型定義"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import re


class CheckType(Enum):
    """チェック方法の種類"""
    REGEX_FORBIDDEN = "regex_forbidden"  # 禁止パターンの正規表現
    REGEX_REQUIRED = "regex_required"    # 必須パターンの正規表現
    LENGTH_MAX = "length_max"            # 最大文字数
    LENGTH_MIN = "length_min"            # 最小文字数
    CUSTOM_FUNCTION = "custom_function"  # カスタムチェック関数
    LLM_SEMANTIC = "llm_semantic"        # LLMによる意味的判断
    NONE = "none"                        # チェックなし（許可ルールなど）


class ViolationAction(Enum):
    """違反時のアクション"""
    REWRITE = "rewrite"  # LLMで書き換え
    REMOVE = "remove"    # 該当部分を削除
    TRIM = "trim"        # 文字数制限で切り詰め
    BLOCK = "block"      # 出力をブロック


@dataclass
class HardRule:
    """正規表現等で機械的にチェック可能なルール（必ず守る）"""
    id: str
    description: str
    check_type: CheckType
    action_on_violation: ViolationAction
    fix_instruction: str
    type: str = "hard"
    pattern: Optional[str] = None
    max_chars: Optional[int] = None
    min_chars: Optional[int] = None
    function_name: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    context_trigger: List[str] = field(default_factory=list)
    prompt_hint: Optional[str] = None

    _compiled_pattern: Optional[re.Pattern] = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if self.pattern:
            self._compiled_pattern = re.compile(self.pattern)

    @classmethod
    def from_dict(cls, data: Dict) -> HardRule:
        check_type_str = data.get("check_type", "llm_semantic")
        try:
            check_type = CheckType(check_type_str)
        except ValueError:
            check_type = CheckType.LLM_SEMANTIC

        action_str = data.get("action_on_violation", "rewrite")
        try:
            action = ViolationAction(action_str)
        except ValueError:
            action = ViolationAction.REWRITE

        return cls(
            id=data["id"],
            description=data["description"],
            check_type=check_type,
            action_on_violation=action,
            fix_instruction=data.get("fix_instruction", ""),
            type=data.get("type", "hard"),
            pattern=data.get("pattern"),
            max_chars=data.get("max_chars"),
            min_chars=data.get("min_chars"),
            function_name=data.get("function_name"),
            params=data.get("params", {}),
            context_trigger=data.get("context_trigger", []),
            prompt_hint=data.get("prompt_hint"),
        )

    def check(self, text: str, context: Optional[Dict] = None) -> Optional[str]:
        """
        違反があれば違反内容を返す。なければNone。
        LLM_SEMANTIC や CUSTOM_FUNCTION はここでは処理しない。
        """
        if self.check_type == CheckType.REGEX_FORBIDDEN:
            if self._compiled_pattern:
                match = self._compiled_pattern.search(text)
                if match:
                    return f"禁止パターン検出: '{match.group()}'"

        elif self.check_type == CheckType.REGEX_REQUIRED:
            if self._compiled_pattern:
                if not self._compiled_pattern.search(text):
                    return f"必須パターンが見つかりません: {self.pattern}"

        elif self.check_type == CheckType.LENGTH_MAX:
            if self.max_chars and len(text) > self.max_chars:
                return f"文字数超過: {len(text)} > {self.max_chars}"

        elif self.check_type == CheckType.LENGTH_MIN:
            if self.min_chars and len(text) < self.min_chars:
                return f"文字数不足: {len(text)} < {self.min_chars}"

        return None


@dataclass
class SoftRule:
    """LLMによる意味的判断が必要なルール（推奨）"""
    id: str
    description: str
    check_type: CheckType
    action_on_violation: ViolationAction
    fix_instruction: str
    type: str = "soft"
    prompt_hint: Optional[str] = None
    function_name: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    context_trigger: List[str] = field(default_factory=list)
    condition: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict) -> SoftRule:
        check_type_str = data.get("check_type", "llm_semantic")
        try:
            check_type = CheckType(check_type_str)
        except ValueError:
            check_type = CheckType.LLM_SEMANTIC

        action_str = data.get("action_on_violation", "rewrite")
        try:
            action = ViolationAction(action_str)
        except ValueError:
            action = ViolationAction.REWRITE

        return cls(
            id=data["id"],
            description=data["description"],
            check_type=check_type,
            action_on_violation=action,
            fix_instruction=data.get("fix_instruction", ""),
            type=data.get("type", "soft"),
            prompt_hint=data.get("prompt_hint"),
            function_name=data.get("function_name"),
            params=data.get("params", {}),
            context_trigger=data.get("context_trigger", []),
            condition=data.get("condition"),
        )


@dataclass
class StateDependentRule:
    """ゲーム状態に依存するルール"""
    id: str
    description: str
    condition: Dict[str, Any]
    check_type: CheckType
    action_on_violation: Optional[ViolationAction] = None
    fix_instruction: Optional[str] = None
    required_elements: List[str] = field(default_factory=list)
    allow_nsfw: bool = False
    prompt_hint: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict) -> StateDependentRule:
        check_type_str = data.get("check_type", "llm_semantic")
        try:
            check_type = CheckType(check_type_str)
        except ValueError:
            check_type = CheckType.LLM_SEMANTIC

        action = None
        if data.get("action_on_violation"):
            try:
                action = ViolationAction(data["action_on_violation"])
            except ValueError:
                action = ViolationAction.REWRITE

        return cls(
            id=data["id"],
            description=data["description"],
            condition=data.get("condition", {}),
            check_type=check_type,
            action_on_violation=action,
            fix_instruction=data.get("fix_instruction"),
            required_elements=data.get("required_elements", []),
            allow_nsfw=data.get("allow_nsfw", False),
            prompt_hint=data.get("prompt_hint"),
        )


@dataclass
class StyleRules:
    """スタイルガイドライン"""
    tone_markers: Dict[str, List[str]] = field(default_factory=dict)
    forbidden_patterns: Dict[str, List[str]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict) -> StyleRules:
        return cls(
            tone_markers=data.get("tone_markers", {}),
            forbidden_patterns=data.get("forbidden_patterns", {}),
        )


@dataclass
class CharacterCore:
    """キャラクターの基本設定"""
    name: str
    age: str
    role_short: str
    backstory_summary_ja: str
    values_ja: str

    @classmethod
    def from_dict(cls, data: Dict) -> CharacterCore:
        return cls(
            name=data.get("name", ""),
            age=data.get("age", ""),
            role_short=data.get("role_short", ""),
            backstory_summary_ja=data.get("backstory_summary_ja", ""),
            values_ja=data.get("values_ja", ""),
        )
