"""出力修正 - 違反がある場合の修正処理"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import re

from .output_validator import ValidationResult, RuleViolation, ViolationSeverity
from ..rules.rule_types import ViolationAction


@dataclass
class FixResult:
    """修正結果"""
    success: bool
    fixed_text: str
    applied_fixes: List[str] = field(default_factory=list)
    remaining_violations: List[RuleViolation] = field(default_factory=list)


class OutputFixer:
    """違反がある場合の修正処理"""

    def __init__(self):
        # ナレーション除去用パターン
        self._narration_patterns = [
            r"（[^）]+）",      # 全角括弧
            r"\([^)]+\)",      # 半角括弧
            r"\*[^*]+\*",      # アスタリスク
            r"【[^】]+】",      # 隅付き括弧
            r"セイラ[:：]\s*",  # 名前:形式
        ]

    def fix(
        self,
        original_text: str,
        validation_result: ValidationResult,
        user_message: str,
        context: Optional[Dict] = None,
    ) -> FixResult:
        """違反を修正"""

        if validation_result.is_valid:
            return FixResult(
                success=True,
                fixed_text=original_text,
                applied_fixes=[],
                remaining_violations=[],
            )

        # ブロック対象はそのまま返す（修正不可）
        block_violations = [
            v for v in validation_result.violations
            if v.suggested_action == ViolationAction.BLOCK
        ]
        if block_violations:
            return FixResult(
                success=False,
                fixed_text="",
                applied_fixes=[],
                remaining_violations=block_violations,
            )

        fixed_text = original_text
        applied_fixes = []

        # 1. 機械的に修正可能なもの（REMOVE, TRIM）を先に処理
        for violation in validation_result.violations:
            if violation.suggested_action == ViolationAction.REMOVE:
                fixed_text, was_fixed = self._apply_remove(fixed_text, violation)
                if was_fixed:
                    applied_fixes.append(f"[{violation.rule_id}] 削除適用")

            elif violation.suggested_action == ViolationAction.TRIM:
                fixed_text, was_fixed = self._apply_trim(fixed_text, violation)
                if was_fixed:
                    applied_fixes.append(f"[{violation.rule_id}] トリム適用")

        # 2. REWRITE が必要なものはLLMで修正
        rewrite_violations = [
            v for v in validation_result.violations
            if v.suggested_action == ViolationAction.REWRITE
        ]

        if rewrite_violations:
            fixed_text = self._apply_llm_rewrite(
                fixed_text,
                rewrite_violations,
                user_message,
            )
            applied_fixes.extend([f"[{v.rule_id}] LLM書き換え" for v in rewrite_violations])

        return FixResult(
            success=True,
            fixed_text=fixed_text,
            applied_fixes=applied_fixes,
            remaining_violations=[],
        )

    def _apply_remove(self, text: str, violation: RuleViolation) -> tuple[str, bool]:
        """REMOVE戦略: 違反部分を削除"""
        original = text

        # ナレーション除去
        for pattern in self._narration_patterns:
            text = re.sub(pattern, "", text)

        # 連続する空白を1つに
        text = re.sub(r"\s+", " ", text)

        return text.strip(), text != original

    def _apply_trim(self, text: str, violation: RuleViolation) -> tuple[str, bool]:
        """TRIM戦略: 文字数制限"""
        max_chars = 200  # デフォルト

        if len(text) <= max_chars:
            return text, False

        # 句点で区切って短くする
        sentences = re.split(r"([。！？])", text)
        result = ""
        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i]
            delimiter = sentences[i + 1] if i + 1 < len(sentences) else ""
            candidate = result + sentence + delimiter
            if len(candidate) > max_chars:
                break
            result = candidate

        if not result:
            # 句点がない場合は単純にカット
            result = text[:max_chars - 3] + "…"

        return result, True

    def _apply_llm_rewrite(
        self,
        text: str,
        violations: List[RuleViolation],
        user_message: str,
    ) -> str:
        """REWRITE戦略: LLMによる書き換え"""

        # LLMクライアントをインポート（循環参照回避）
        try:
            from ..llm_client import llm_client
            from ..settings import settings
        except ImportError:
            print("[OutputFixer] Warning: LLM client not available")
            return text

        fix_instructions = "\n".join([
            f"- [{v.rule_id}] {v.fix_instruction}"
            for v in violations
        ])

        violation_details = "\n".join([
            f"- {v.violation_detail}"
            for v in violations
        ])

        prompt = f"""以下のBot発話を、指示に従って修正してください。
キャラクター（蒼井セイラ）の性格・口調は維持しつつ、ルール違反のみを修正します。

## キャラクター設定
- 19歳の地下アイドル「蒼井セイラ」
- 一人称は「わたし」
- ハキハキとした丁寧語（「〜ですっ！」「〜なんです！」）
- 慌てた時は「はわわ…！」
- 明るく素直で、夢に向かって頑張っている

## 元の発話
{text}

## ユーザーの発言（文脈）
{user_message}

## 検出された違反
{violation_details}

## 修正指示
{fix_instructions}

## 重要
- セリフのみを出力してください
- ナレーションや説明は不要です
- キャラクターの魅力を損なわないように
- 自然な日本語で

## 出力
修正後の発話のみを出力してください。
"""

        try:
            # Fixerは Actor と同じモデルを使う（キャラ一貫性のため）
            fixed = llm_client.chat(
                model=settings.llm.actor_model,
                messages=[{"role": "user", "content": prompt}],
                provider=settings.llm.actor_provider,
            )

            if fixed:
                # 余分な引用符や空白を除去
                fixed = fixed.strip()
                fixed = fixed.strip('"\'')
                return fixed

            return text

        except Exception as e:
            print(f"[OutputFixer] LLM rewrite error: {e}")
            return text

    def fix_quick(
        self,
        text: str,
        violations: List[RuleViolation],
    ) -> FixResult:
        """LLMを使わない高速修正（REMOVE/TRIMのみ）"""
        fixed_text = text
        applied_fixes = []
        remaining = []

        for violation in violations:
            if violation.suggested_action == ViolationAction.REMOVE:
                fixed_text, was_fixed = self._apply_remove(fixed_text, violation)
                if was_fixed:
                    applied_fixes.append(f"[{violation.rule_id}] 削除適用")
                else:
                    remaining.append(violation)

            elif violation.suggested_action == ViolationAction.TRIM:
                fixed_text, was_fixed = self._apply_trim(fixed_text, violation)
                if was_fixed:
                    applied_fixes.append(f"[{violation.rule_id}] トリム適用")
                else:
                    remaining.append(violation)

            elif violation.suggested_action == ViolationAction.BLOCK:
                remaining.append(violation)

            else:
                # REWRITEは残す
                remaining.append(violation)

        return FixResult(
            success=len(remaining) == 0,
            fixed_text=fixed_text,
            applied_fixes=applied_fixes,
            remaining_violations=remaining,
        )
