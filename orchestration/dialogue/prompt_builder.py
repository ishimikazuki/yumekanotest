"""PromptBuilder: LLMプロンプトの構築"""
from __future__ import annotations
from typing import List, Dict, Optional, TYPE_CHECKING

from ..models import UserState, EmotionState
from ..rules.rule_selector import SelectedRules
from ..rules.rule_registry import RuleRegistry

if TYPE_CHECKING:
    from ..memory.structured import UserProfile, Promise, Boundary


class PromptBuilder:
    """
    プロンプトビルダー
    Actor/Fixer向けのLLMプロンプトを構築する。
    """

    def __init__(self, registry: Optional[RuleRegistry] = None):
        self._registry = registry or RuleRegistry.get_instance()

    def build_actor_prompt(
        self,
        user_message: str,
        history: List[Dict],
        state: UserState,
        memories: List[str],
        selected_rules: Optional[SelectedRules] = None,
        instruction_override: Optional[str] = None,
    ) -> str:
        """
        Actor用のユーザープロンプトを構築する。

        Args:
            user_message: ユーザーの入力
            history: 会話履歴
            state: ユーザー状態
            memories: 関連記憶
            selected_rules: 適用ルール
            instruction_override: 強制指示

        Returns:
            str: 構築されたプロンプト
        """
        parts = []

        # 現在の状態
        parts.append(f"## 現在の状態\n{state.to_dict()}")

        # 演技指針
        tone = self._tone_from_emotion(state.emotion)
        parts.append(f"\n## 演技指針(PAD由来)\n{tone}")

        # 長期記憶
        if memories:
            memory_text = "\n".join([f"- {m}" for m in memories])
            parts.append(f"\n## 関連する長期記憶\n{memory_text}")
        else:
            parts.append("\n## 関連する長期記憶\n特になし")

        # ルール要約
        if selected_rules:
            parts.append(f"\n{selected_rules.summary}")

        # 強制指示
        if instruction_override:
            parts.append(f"\n## 強制指示\n{instruction_override}")

        # 会話履歴（直近3件）
        recent_history = history[-3:] if history else []
        if recent_history:
            history_text = "\n".join([
                f"- {h.get('role', 'unknown')}: {h.get('content', '')}"
                for h in recent_history
            ])
            parts.append(f"\n## 直近会話履歴\n{history_text}")

        # ユーザー発話
        parts.append(f"\n## ユーザー発話\n{user_message}")

        return "\n".join(parts)

    def build_fixer_prompt(
        self,
        original_text: str,
        user_message: str,
        violations: List[str],
        fix_instructions: List[str],
    ) -> str:
        """
        Fixer用のプロンプトを構築する。

        Args:
            original_text: 修正前のテキスト
            user_message: ユーザーの入力
            violations: 違反内容のリスト
            fix_instructions: 修正指示のリスト

        Returns:
            str: 構築されたプロンプト
        """
        char_core = self._registry.get_character_core()
        char_info = ""
        if char_core:
            char_info = f"""## キャラクター設定
- 名前: {char_core.name}
- {char_core.role_short}、{char_core.age}
- 一人称は「わたし」
- ハキハキとした丁寧語（「〜ですっ！」「〜なんです！」）
- 慌てた時は「はわわ…！」
- 明るく素直で、夢に向かって頑張っている
"""

        violations_text = "\n".join([f"- {v}" for v in violations])
        instructions_text = "\n".join([f"- {i}" for i in fix_instructions])

        return f"""{char_info}

## 元の発話
{original_text}

## ユーザーの発言（文脈）
{user_message}

## 検出された違反
{violations_text}

## 修正指示
{instructions_text}

## 重要
- セリフのみを出力してください
- ナレーションや説明は不要です
- キャラクターの魅力を損なわないように
- 自然な日本語で

## 出力
修正後の発話のみを出力してください。
"""

    def _tone_from_emotion(self, emo: EmotionState) -> str:
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

    def build_actor_prompt_v2(
        self,
        user_message: str,
        history: List[Dict],
        state: UserState,
        user_profile: Optional["UserProfile"] = None,
        promises: Optional[List["Promise"]] = None,
        boundaries: Optional[List["Boundary"]] = None,
        retrieved_episodes: Optional[List[str]] = None,
        selected_rules: Optional[SelectedRules] = None,
        instruction_override: Optional[str] = None,
    ) -> str:
        """
        Actor用のユーザープロンプトを構築する（v2: 改善版注入順序）

        注入順序:
        1. Persona（キャラクター設定）
        2. UserProfile（ユーザー情報）
        3. 約束/NG（守るべきこと）
        4. 検索エピソード（Vector検索結果）
        5. 短期記憶（直近会話）
        6. ユーザー発話

        Args:
            user_message: ユーザーの入力
            history: 会話履歴
            state: ユーザー状態
            user_profile: ユーザープロフィール
            promises: 約束リスト
            boundaries: 境界線（NG）リスト
            retrieved_episodes: 検索されたエピソード
            selected_rules: 適用ルール
            instruction_override: 強制指示

        Returns:
            str: 構築されたプロンプト
        """
        parts = []

        # 1. Persona（キャラクター設定）
        char_core = self._registry.get_character_core()
        if char_core:
            parts.append(f"""## キャラクター設定（Persona）
- 名前: {char_core.name}
- {char_core.role_short}、{char_core.age}
- 一人称は「わたし」
- ハキハキとした丁寧語（「〜ですっ！」「〜なんです！」）
- 慌てた時は「はわわ…！」
- 明るく素直で、夢に向かって頑張っている""")

        # 演技指針
        tone = self._tone_from_emotion(state.emotion)
        parts.append(f"\n## 演技指針\n{tone}")

        # 2. UserProfile（ユーザー情報）
        if user_profile:
            profile_lines = ["## ユーザー情報"]
            if user_profile.name:
                profile_lines.append(f"- 名前: {user_profile.name}")
            if user_profile.age:
                profile_lines.append(f"- 年齢: {user_profile.age}歳")
            if user_profile.occupation:
                profile_lines.append(f"- 職業: {user_profile.occupation}")
            if user_profile.location:
                profile_lines.append(f"- 住所: {user_profile.location}")
            if user_profile.hobbies:
                profile_lines.append(f"- 趣味: {', '.join(user_profile.hobbies)}")
            if user_profile.preferences:
                for key, value in user_profile.preferences.items():
                    profile_lines.append(f"- 好きな{key}: {value}")

            if len(profile_lines) > 1:
                parts.append("\n" + "\n".join(profile_lines))

        # 3a. 約束（守るべきこと）
        if promises:
            promise_lines = ["## 守るべき約束"]
            for p in promises:
                status_mark = "✓" if p.status == "fulfilled" else "○"
                promise_lines.append(f"- [{status_mark}] {p.content}")
            parts.append("\n" + "\n".join(promise_lines))

        # 3b. 境界線（NG）
        if boundaries:
            boundary_lines = ["## 触れてはいけない話題・行動（NG）"]
            for b in boundaries:
                severity_mark = "⚠️" if b.severity >= 0.8 else "△"
                boundary_lines.append(f"- {severity_mark} {b.content}（{b.category}）")
            boundary_lines.append("\n※ これらの話題には触れないでください")
            parts.append("\n" + "\n".join(boundary_lines))

        # ルール要約
        if selected_rules:
            parts.append(f"\n{selected_rules.summary}")

        # 強制指示
        if instruction_override:
            parts.append(f"\n## 強制指示\n{instruction_override}")

        # 4. 検索エピソード（Vector検索結果）
        if retrieved_episodes:
            episode_lines = ["## 関連する過去のエピソード"]
            for ep in retrieved_episodes:
                episode_lines.append(f"- {ep}")
            parts.append("\n" + "\n".join(episode_lines))

        # 5. 短期記憶（直近会話）
        recent_history = history[-5:] if history else []
        if recent_history:
            history_text = "\n".join([
                f"- {h.get('role', 'unknown')}: {h.get('content', '')}"
                for h in recent_history
            ])
            parts.append(f"\n## 直近の会話\n{history_text}")

        # 6. ユーザー発話
        parts.append(f"\n## ユーザーの発言\n{user_message}")

        return "\n".join(parts)
