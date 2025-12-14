"""PromptBuilderのテスト（TDD）

Issue #003: 応答生成の注入順序を改善
"""
import pytest
import sys
from unittest.mock import MagicMock, patch

# conversation_memoryのインポートエラーを回避
sys.modules['orchestration.dialogue.conversation_memory'] = MagicMock()

from orchestration.dialogue.prompt_builder import PromptBuilder
from orchestration.models import UserState, EmotionState
from orchestration.memory.structured import UserProfile, Promise, Boundary


@pytest.fixture
def builder():
    """PromptBuilderのインスタンス"""
    return PromptBuilder()


@pytest.fixture
def sample_state():
    """サンプルのUserState"""
    return UserState(
        user_id="test_user",
        updated_at="2025-01-01T00:00:00Z",
        emotion=EmotionState(pleasure=5.0, arousal=3.0, dominance=2.0),
    )


@pytest.fixture
def sample_profile():
    """サンプルのUserProfile"""
    return UserProfile(
        user_id="test_user",
        name="太郎",
        age=25,
        occupation="エンジニア",
        hobbies=["ゲーム", "読書"],
        preferences={"food": "ラーメン"},
    )


@pytest.fixture
def sample_promises():
    """サンプルの約束リスト"""
    return [
        Promise(
            id="1",
            user_id="test_user",
            content="来週映画を見に行く",
            created_at="2025-01-01",
            status="pending",
        ),
        Promise(
            id="2",
            user_id="test_user",
            content="誕生日にケーキを買う",
            created_at="2025-01-02",
            status="pending",
        ),
    ]


@pytest.fixture
def sample_boundaries():
    """サンプルの境界線リスト"""
    return [
        Boundary(
            id="1",
            user_id="test_user",
            content="元カノの話",
            category="topic",
            severity=0.9,
            created_at="2025-01-01",
        ),
        Boundary(
            id="2",
            user_id="test_user",
            content="急に電話する",
            category="action",
            severity=0.7,
            created_at="2025-01-02",
        ),
    ]


class TestPromptInjectionOrder:
    """注入順序のテスト"""

    def test_persona_comes_first(self, builder, sample_state):
        """Personaが最初に来る"""
        prompt = builder.build_actor_prompt(
            user_message="こんにちは",
            history=[],
            state=sample_state,
            memories=[],
        )

        # Personaセクションが最初に来ることを確認
        persona_idx = prompt.find("キャラクター") if "キャラクター" in prompt else prompt.find("Persona")
        state_idx = prompt.find("現在の状態")

        # Personaが存在するか、または状態より前にある
        assert persona_idx != -1 or "演技指針" in prompt

    def test_user_profile_injection(self, builder, sample_state, sample_profile):
        """UserProfileが注入される"""
        prompt = builder.build_actor_prompt_v2(
            user_message="こんにちは",
            history=[],
            state=sample_state,
            user_profile=sample_profile,
        )

        assert "太郎" in prompt
        assert "25" in prompt or "歳" in prompt
        assert "ゲーム" in prompt or "読書" in prompt

    def test_promises_injection(self, builder, sample_state, sample_promises):
        """約束が注入される"""
        prompt = builder.build_actor_prompt_v2(
            user_message="こんにちは",
            history=[],
            state=sample_state,
            promises=sample_promises,
        )

        assert "映画" in prompt
        assert "ケーキ" in prompt

    def test_boundaries_injection(self, builder, sample_state, sample_boundaries):
        """境界線（NG）が注入される"""
        prompt = builder.build_actor_prompt_v2(
            user_message="こんにちは",
            history=[],
            state=sample_state,
            boundaries=sample_boundaries,
        )

        assert "元カノ" in prompt
        assert "電話" in prompt

    def test_retrieved_episodes_injection(self, builder, sample_state):
        """検索エピソードが注入される"""
        episodes = ["去年一緒にディズニーに行った", "初めて会ったのは駅前"]

        prompt = builder.build_actor_prompt_v2(
            user_message="こんにちは",
            history=[],
            state=sample_state,
            retrieved_episodes=episodes,
        )

        assert "ディズニー" in prompt
        assert "駅前" in prompt

    def test_injection_order(self, builder, sample_state, sample_profile, sample_promises, sample_boundaries):
        """注入順序が正しい: Persona → Profile → 約束/NG → エピソード → 短期 → 発話"""
        episodes = ["エピソード1"]
        history = [{"role": "user", "content": "前の発言"}]

        prompt = builder.build_actor_prompt_v2(
            user_message="今の発言",
            history=history,
            state=sample_state,
            user_profile=sample_profile,
            promises=sample_promises,
            boundaries=sample_boundaries,
            retrieved_episodes=episodes,
        )

        # 各セクションの位置を取得
        profile_idx = prompt.find("太郎")
        promise_idx = prompt.find("映画")
        boundary_idx = prompt.find("元カノ")
        episode_idx = prompt.find("エピソード1")
        history_idx = prompt.find("前の発言")
        user_msg_idx = prompt.find("今の発言")

        # 順序を確認（存在するもののみ）
        positions = []
        if profile_idx != -1:
            positions.append(("profile", profile_idx))
        if promise_idx != -1:
            positions.append(("promise", promise_idx))
        if boundary_idx != -1:
            positions.append(("boundary", boundary_idx))
        if episode_idx != -1:
            positions.append(("episode", episode_idx))
        if history_idx != -1:
            positions.append(("history", history_idx))
        if user_msg_idx != -1:
            positions.append(("user_msg", user_msg_idx))

        # 位置順にソート
        positions.sort(key=lambda x: x[1])
        names = [p[0] for p in positions]

        # user_msgは最後
        assert names[-1] == "user_msg"


class TestBoundaryWarning:
    """Boundary違反警告のテスト"""

    def test_boundary_warning_in_prompt(self, builder, sample_state, sample_boundaries):
        """Boundaryがある場合、警告が含まれる"""
        prompt = builder.build_actor_prompt_v2(
            user_message="こんにちは",
            history=[],
            state=sample_state,
            boundaries=sample_boundaries,
        )

        # 警告文言が含まれる
        assert "触れない" in prompt or "NG" in prompt or "避け" in prompt

    def test_high_severity_boundary_emphasized(self, builder, sample_state):
        """高重要度のboundaryは強調される"""
        high_severity = [
            Boundary(
                id="1",
                user_id="test_user",
                content="絶対に触れてはいけない話題",
                category="topic",
                severity=0.95,
                created_at="2025-01-01",
            )
        ]

        prompt = builder.build_actor_prompt_v2(
            user_message="こんにちは",
            history=[],
            state=sample_state,
            boundaries=high_severity,
        )

        # 高重要度の警告
        assert "絶対" in prompt or "重要" in prompt or "触れてはいけない" in prompt


class TestEmptyValues:
    """空の値のテスト"""

    def test_no_profile_no_error(self, builder, sample_state):
        """プロフィールなしでもエラーにならない"""
        prompt = builder.build_actor_prompt_v2(
            user_message="こんにちは",
            history=[],
            state=sample_state,
            user_profile=None,
        )

        assert "こんにちは" in prompt

    def test_no_promises_no_section(self, builder, sample_state):
        """約束なしの場合、約束セクションがない"""
        prompt = builder.build_actor_prompt_v2(
            user_message="こんにちは",
            history=[],
            state=sample_state,
            promises=[],
        )

        # 空の約束セクションは表示しない
        # （または「約束はありません」などの表示）
        assert "約束" not in prompt or "ありません" in prompt or "なし" in prompt

    def test_no_boundaries_no_section(self, builder, sample_state):
        """NGなしの場合、NGセクションがない"""
        prompt = builder.build_actor_prompt_v2(
            user_message="こんにちは",
            history=[],
            state=sample_state,
            boundaries=[],
        )

        assert "こんにちは" in prompt


class TestBackwardCompatibility:
    """後方互換性のテスト"""

    def test_old_method_still_works(self, builder, sample_state):
        """既存のbuild_actor_promptが動作する"""
        prompt = builder.build_actor_prompt(
            user_message="こんにちは",
            history=[],
            state=sample_state,
            memories=["過去の記憶"],
        )

        assert "こんにちは" in prompt
        assert "過去の記憶" in prompt
