"""出力検証 - ルール違反チェック（正規表現+LLM）"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
from enum import Enum
import json

from ..rules.rule_types import HardRule, SoftRule, StateDependentRule, ViolationAction, CheckType
from ..rules.rule_selector import SelectedRules


class ViolationSeverity(Enum):
    """違反の重大度"""
    CRITICAL = "critical"  # 即座にブロック
    HIGH = "high"          # 修正必須
    MEDIUM = "medium"      # 修正推奨
    LOW = "low"            # 警告のみ


@dataclass
class RuleViolation:
    """ルール違反の詳細"""
    rule_id: str
    rule_name: str
    description: str
    severity: ViolationSeverity
    violation_detail: str
    suggested_action: ViolationAction
    fix_instruction: str
    matched_text: Optional[str] = None


@dataclass
class ValidationResult:
    """検証結果"""
    is_valid: bool
    violations: List[RuleViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def has_critical(self) -> bool:
        return any(v.severity == ViolationSeverity.CRITICAL for v in self.violations)

    @property
    def needs_fix(self) -> bool:
        return any(
            v.severity in [ViolationSeverity.CRITICAL, ViolationSeverity.HIGH]
            for v in self.violations
        )

    def get_fix_instructions(self) -> List[str]:
        return [v.fix_instruction for v in self.violations if v.fix_instruction]

    def get_violations_summary(self) -> str:
        """違反の要約を生成"""
        if not self.violations:
            return "違反なし"
        lines = []
        for v in self.violations:
            lines.append(f"- [{v.rule_id}] {v.violation_detail}")
        return "\n".join(lines)


class OutputValidator:
    """出力のルール違反チェック（HardRule + SoftRule）"""

    def __init__(self):
        self._custom_checkers: Dict[str, Callable] = {}
        self._register_default_checkers()

    def _register_default_checkers(self):
        """デフォルトのカスタムチェッカーを登録"""
        self._custom_checkers["check_ehehe_frequency"] = self._check_ehehe_frequency
        self._custom_checkers["check_topic_stagnation"] = self._check_topic_stagnation
        self._custom_checkers["check_length"] = self._check_length

    def register_checker(self, name: str, func: Callable) -> None:
        """カスタムチェッカーを登録"""
        self._custom_checkers[name] = func

    def validate(
        self,
        output_text: str,
        user_message: str,
        selected_rules: SelectedRules,
        history: List[Dict],
        context: Optional[Dict] = None,
    ) -> ValidationResult:
        """出力テキストを検証"""
        violations = []
        warnings = []

        # 1. HardRule チェック（正規表現ベース）
        for rule in selected_rules.hard_rules:
            violation = self._check_hard_rule(rule, output_text, history, context)
            if violation:
                violations.append(violation)

        # 2. SoftRule チェック（カスタム関数）
        for rule in selected_rules.soft_rules:
            if rule.check_type == CheckType.CUSTOM_FUNCTION and rule.function_name:
                violation = self._check_custom_rule(rule, output_text, history, context)
                if violation:
                    violations.append(violation)

        # 3. StateDependentRule チェック
        for rule in selected_rules.state_dependent_rules:
            violation = self._check_state_dependent_rule(rule, output_text, user_message)
            if violation:
                violations.append(violation)

        # 4. SoftRule LLMチェック - Hardで既にCRITICALならスキップ
        if not any(v.severity == ViolationSeverity.CRITICAL for v in violations):
            llm_soft_rules = [
                r for r in selected_rules.soft_rules
                if r.check_type == CheckType.LLM_SEMANTIC
            ]
            if llm_soft_rules:
                soft_violations = self._check_soft_rules_llm(
                    llm_soft_rules,
                    output_text,
                    user_message,
                    history,
                )
                violations.extend(soft_violations)

        is_valid = len(violations) == 0
        return ValidationResult(is_valid=is_valid, violations=violations, warnings=warnings)

    def _check_hard_rule(
        self,
        rule: HardRule,
        text: str,
        history: List[Dict],
        context: Optional[Dict],
    ) -> Optional[RuleViolation]:
        """HardRuleの検証"""

        # カスタム関数チェック
        if rule.check_type == CheckType.CUSTOM_FUNCTION and rule.function_name:
            checker = self._custom_checkers.get(rule.function_name)
            if checker:
                result = checker(text, history, rule.params)
                if result:
                    return RuleViolation(
                        rule_id=rule.id,
                        rule_name=rule.id,
                        description=rule.description,
                        severity=ViolationSeverity.HIGH,
                        violation_detail=result,
                        suggested_action=rule.action_on_violation,
                        fix_instruction=rule.fix_instruction,
                    )
            return None

        # LLM_SEMANTICはここでは処理しない
        if rule.check_type == CheckType.LLM_SEMANTIC:
            return None

        # 正規表現等の標準チェック
        violation_msg = rule.check(text, context)
        if violation_msg:
            severity = (
                ViolationSeverity.CRITICAL
                if rule.action_on_violation == ViolationAction.BLOCK
                else ViolationSeverity.HIGH
            )
            return RuleViolation(
                rule_id=rule.id,
                rule_name=rule.id,
                description=rule.description,
                severity=severity,
                violation_detail=violation_msg,
                suggested_action=rule.action_on_violation,
                fix_instruction=rule.fix_instruction,
            )
        return None

    def _check_custom_rule(
        self,
        rule: SoftRule,
        text: str,
        history: List[Dict],
        context: Optional[Dict],
    ) -> Optional[RuleViolation]:
        """SoftRuleのカスタム関数チェック"""
        if not rule.function_name:
            return None

        checker = self._custom_checkers.get(rule.function_name)
        if not checker:
            return None

        result = checker(text, history, rule.params)
        if result:
            return RuleViolation(
                rule_id=rule.id,
                rule_name=rule.id,
                description=rule.description,
                severity=ViolationSeverity.MEDIUM,
                violation_detail=result,
                suggested_action=rule.action_on_violation,
                fix_instruction=rule.fix_instruction,
            )
        return None

    def _check_ehehe_frequency(
        self,
        text: str,
        history: List[Dict],
        params: Dict,
    ) -> Optional[str]:
        """「えへへ」の使用頻度チェック"""
        if "えへへ" not in text:
            return None

        min_interval = params.get("min_interval", 4)

        # 直近の履歴をチェック
        recent_assistant_msgs = [
            h.get("content", "")
            for h in history[-min_interval:]
            if h.get("role") == "assistant"
        ]

        for msg in recent_assistant_msgs:
            if "えへへ" in msg:
                return f"「えへへ」が{min_interval}ターン以内に既に使用されています"

        return None

    def _check_topic_stagnation(
        self,
        text: str,
        history: List[Dict],
        params: Dict,
    ) -> Optional[str]:
        """話題の停滞チェック（簡易実装）"""
        # 実際の実装ではLLMで判断するか、キーワード抽出が必要
        # ここでは簡易的にスキップ
        return None

    def _check_length(
        self,
        text: str,
        history: List[Dict],
        params: Dict,
    ) -> Optional[str]:
        """文字数チェック"""
        normal_max = params.get("normal_max", 150)
        # ここでは通常会話として判定
        if len(text) > normal_max:
            return f"文字数超過: {len(text)} > {normal_max}"
        return None

    def _check_state_dependent_rule(
        self,
        rule: StateDependentRule,
        text: str,
        user_message: str,
    ) -> Optional[RuleViolation]:
        """StateDependentRuleの検証"""
        if rule.check_type == CheckType.NONE:
            return None

        # required_elementsのチェック
        if rule.required_elements:
            missing = [elem for elem in rule.required_elements if elem not in text]
            if missing:
                return RuleViolation(
                    rule_id=rule.id,
                    rule_name=rule.id,
                    description=rule.description,
                    severity=ViolationSeverity.HIGH,
                    violation_detail=f"必須要素が不足: {', '.join(missing)}",
                    suggested_action=rule.action_on_violation or ViolationAction.REWRITE,
                    fix_instruction=rule.fix_instruction or "",
                )

        return None

    def _check_soft_rules_llm(
        self,
        rules: List[SoftRule],
        text: str,
        user_message: str,
        history: List[Dict],
    ) -> List[RuleViolation]:
        """SoftRulesをLLMで一括検証"""
        if not rules:
            return []

        # LLMクライアントをインポート（循環参照回避）
        try:
            from ..llm_client import llm_client
            from ..settings import settings
        except ImportError:
            print("[OutputValidator] Warning: LLM client not available")
            return []

        # LLMに一括で検証させる
        check_items = "\n".join([
            f"- [{rule.id}] {rule.description}"
            + (f" ({rule.prompt_hint})" if rule.prompt_hint else "")
            for rule in rules
        ])

        prompt = f"""以下のルールに対して、Bot出力が違反していないか確認してください。

## ルール一覧
{check_items}

## ユーザー入力
{user_message}

## Bot出力
{text}

## 出力形式（JSON）
違反があるルールのIDと違反内容を配列で返してください。違反がなければ空配列。
例: {{"violations": [{{"rule_id": "no_parrot", "detail": "ユーザーの「疲れた」をそのまま繰り返している"}}]}}
違反なしの場合: {{"violations": []}}
"""

        try:
            response = llm_client.chat(
                model=settings.llm.observer_model,
                messages=[{"role": "user", "content": prompt}],
                provider=settings.llm.observer_provider,
                response_format={"type": "json_object"},
            )

            if not response:
                return []

            # JSONパース
            cleaned = response.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned)

            violations = []
            for v in data.get("violations", []):
                rule = next((r for r in rules if r.id == v.get("rule_id")), None)
                if rule:
                    violations.append(RuleViolation(
                        rule_id=rule.id,
                        rule_name=rule.id,
                        description=rule.description,
                        severity=ViolationSeverity.MEDIUM,
                        violation_detail=v.get("detail", ""),
                        suggested_action=rule.action_on_violation,
                        fix_instruction=rule.fix_instruction,
                    ))
            return violations

        except Exception as e:
            print(f"[OutputValidator] SoftRule LLM check error: {e}")
            return []

    def validate_quick(
        self,
        output_text: str,
        selected_rules: SelectedRules,
        history: List[Dict],
    ) -> ValidationResult:
        """HardRuleのみの高速検証（LLMを使わない）"""
        violations = []

        for rule in selected_rules.hard_rules:
            if rule.check_type in [CheckType.REGEX_FORBIDDEN, CheckType.REGEX_REQUIRED,
                                   CheckType.LENGTH_MAX, CheckType.LENGTH_MIN]:
                violation = self._check_hard_rule(rule, output_text, history, None)
                if violation:
                    violations.append(violation)

        is_valid = len(violations) == 0
        return ValidationResult(is_valid=is_valid, violations=violations)
