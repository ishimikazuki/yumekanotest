"""ルールレジストリ - 振る舞いルールの唯一のソース"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any
import json

from .rule_types import (
    HardRule,
    SoftRule,
    StateDependentRule,
    StyleRules,
    CharacterCore,
)


class RuleRegistry:
    """
    振る舞いルールの唯一のソース（Single Source of Truth）
    シングルトンパターンで実装。
    """

    _instance: Optional[RuleRegistry] = None

    def __init__(self, rules_path: Path):
        self._rules_path = rules_path
        self._hard_rules: Dict[str, HardRule] = {}
        self._soft_rules: Dict[str, SoftRule] = {}
        self._state_dependent_rules: Dict[str, StateDependentRule] = {}
        self._style_rules: Optional[StyleRules] = None
        self._character_core: Optional[CharacterCore] = None
        self._custom_checkers: Dict[str, Callable] = {}
        self._raw_data: Dict[str, Any] = {}
        self._load_rules()

    @classmethod
    def get_instance(cls, rules_path: Optional[Path] = None) -> RuleRegistry:
        """シングルトンインスタンスを取得"""
        if cls._instance is None:
            if rules_path is None:
                # デフォルトパス
                rules_path = Path(__file__).parent.parent.parent / "data" / "rules" / "behavior_rules.json"
            cls._instance = cls(rules_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """インスタンスをリセット（テスト用）"""
        cls._instance = None

    def _load_rules(self) -> None:
        """JSONからルールをロード"""
        if not self._rules_path.exists():
            print(f"[RuleRegistry] Warning: Rules file not found at {self._rules_path}")
            return

        with open(self._rules_path, encoding="utf-8") as f:
            self._raw_data = json.load(f)

        # CharacterCore
        if "character_core" in self._raw_data:
            self._character_core = CharacterCore.from_dict(self._raw_data["character_core"])

        # HardRules
        for rule_data in self._raw_data.get("hard_rules", []):
            rule = HardRule.from_dict(rule_data)
            self._hard_rules[rule.id] = rule

        # SoftRules
        for rule_data in self._raw_data.get("soft_rules", []):
            rule = SoftRule.from_dict(rule_data)
            self._soft_rules[rule.id] = rule

        # StateDependentRules
        for rule_data in self._raw_data.get("state_dependent_rules", []):
            rule = StateDependentRule.from_dict(rule_data)
            self._state_dependent_rules[rule.id] = rule

        # StyleRules
        self._style_rules = StyleRules.from_dict(self._raw_data.get("style_rules", {}))

        print(f"[RuleRegistry] Loaded {len(self._hard_rules)} hard rules, "
              f"{len(self._soft_rules)} soft rules, "
              f"{len(self._state_dependent_rules)} state-dependent rules")

    def register_custom_checker(self, name: str, func: Callable) -> None:
        """カスタムチェック関数を登録"""
        self._custom_checkers[name] = func

    def get_custom_checker(self, name: str) -> Optional[Callable]:
        """カスタムチェック関数を取得"""
        return self._custom_checkers.get(name)

    def get_hard_rules(self) -> List[HardRule]:
        """全てのハードルールを取得"""
        return list(self._hard_rules.values())

    def get_hard_rule(self, rule_id: str) -> Optional[HardRule]:
        """指定IDのハードルールを取得"""
        return self._hard_rules.get(rule_id)

    def get_soft_rules(self) -> List[SoftRule]:
        """全てのソフトルールを取得"""
        return list(self._soft_rules.values())

    def get_soft_rule(self, rule_id: str) -> Optional[SoftRule]:
        """指定IDのソフトルールを取得"""
        return self._soft_rules.get(rule_id)

    def get_state_dependent_rules(self) -> List[StateDependentRule]:
        """全ての状態依存ルールを取得"""
        return list(self._state_dependent_rules.values())

    def get_state_dependent_rule(self, rule_id: str) -> Optional[StateDependentRule]:
        """指定IDの状態依存ルールを取得"""
        return self._state_dependent_rules.get(rule_id)

    def get_style_rules(self) -> Optional[StyleRules]:
        """スタイルルールを取得"""
        return self._style_rules

    def get_character_core(self) -> Optional[CharacterCore]:
        """キャラクター基本設定を取得"""
        return self._character_core

    def get_scenes(self) -> List[Dict[str, Any]]:
        """シーン定義を取得"""
        return self._raw_data.get("scenes", [])

    def get_memory_rules(self) -> Dict[str, str]:
        """メモリルールを取得"""
        return self._raw_data.get("memory_rules", {})

    def get_output_format_rules(self) -> Dict[str, str]:
        """出力フォーマットルールを取得"""
        return self._raw_data.get("output_format_rules", {})

    def reload(self) -> None:
        """ルールをリロード（開発時のホットリロード用）"""
        self._hard_rules.clear()
        self._soft_rules.clear()
        self._state_dependent_rules.clear()
        self._load_rules()
        print("[RuleRegistry] Rules reloaded")

    def get_all_rules_summary(self) -> str:
        """全ルールの要約テキストを生成"""
        lines = ["# 振る舞いルール要約"]

        if self._character_core:
            lines.append(f"\n## キャラクター: {self._character_core.name}")
            lines.append(f"- {self._character_core.role_short}、{self._character_core.age}")
            lines.append(f"- {self._character_core.backstory_summary_ja[:100]}...")

        lines.append("\n## 必須ルール（Hard Rules）")
        for rule in self._hard_rules.values():
            lines.append(f"- [{rule.id}] {rule.description}")

        lines.append("\n## 推奨ルール（Soft Rules）")
        for rule in self._soft_rules.values():
            lines.append(f"- [{rule.id}] {rule.description}")

        return "\n".join(lines)
