"""構造化メモリのテスト（TDD: テストを先に書く）

Issue #002: 構造化メモリ（プロフィール/約束/NG）の実装
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

# インポートはまだ存在しないが、期待するAPIを定義
# from orchestration.memory.structured import (
#     StructuredMemoryManager,
#     UserProfile,
#     Promise,
#     Boundary,
# )


@pytest.fixture
def mock_supabase():
    """Supabaseクライアントのモック"""
    with patch("orchestration.memory.structured.get_supabase") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def manager(mock_supabase):
    """StructuredMemoryManagerのインスタンス"""
    from orchestration.memory.structured import StructuredMemoryManager
    return StructuredMemoryManager(user_id="test_user_123")


class TestUserProfile:
    """ユーザープロフィールのテスト"""

    def test_save_profile_name(self, manager, mock_supabase):
        """名前を保存できる"""
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{"name": "太郎"}])

        manager.save_profile("name", "太郎")

        mock_supabase.table.assert_called_with("user_profiles")

    def test_save_profile_age(self, manager, mock_supabase):
        """年齢を保存できる"""
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{"age": 25}])

        manager.save_profile("age", 25)

        mock_supabase.table.assert_called_with("user_profiles")

    def test_get_profile_returns_dataclass(self, manager, mock_supabase):
        """プロフィール取得でUserProfileが返る"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data={
                "user_id": "test_user_123",
                "name": "太郎",
                "age": 25,
                "occupation": "エンジニア",
                "location": "東京",
                "birthday": "1999-01-01",
                "hobbies": ["ゲーム", "読書"],
                "preferences": {"food": "ラーメン"}
            }
        )

        from orchestration.memory.structured import UserProfile
        profile = manager.get_profile()

        assert isinstance(profile, UserProfile)
        assert profile.name == "太郎"
        assert profile.age == 25

    def test_get_profile_empty_returns_default(self, manager, mock_supabase):
        """プロフィールがない場合はデフォルト値"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=None)

        from orchestration.memory.structured import UserProfile
        profile = manager.get_profile()

        assert isinstance(profile, UserProfile)
        assert profile.name is None

    def test_save_profile_hobby_appends(self, manager, mock_supabase):
        """趣味は追加される"""
        # 既存データ
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(
            data={"hobbies": ["ゲーム"]}
        )
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{}])

        manager.save_profile("hobby", "読書")

        # upsertが呼ばれ、hobbiesに"読書"が追加されている
        call_args = mock_supabase.table.return_value.upsert.call_args
        assert "読書" in call_args[0][0].get("hobbies", [])


class TestPromise:
    """約束のテスト"""

    def test_save_promise(self, manager, mock_supabase):
        """約束を保存できる"""
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "promise_1", "content": "来週映画を見に行く"}]
        )

        result = manager.save_promise("来週映画を見に行く")

        assert result is not None
        mock_supabase.table.assert_called_with("promises")

    def test_save_promise_with_due_date(self, manager, mock_supabase):
        """期日付きで約束を保存できる"""
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "promise_1", "due_date": "2025-01-01"}]
        )

        result = manager.save_promise("来週映画を見に行く", due_date="2025-01-01")

        call_args = mock_supabase.table.return_value.insert.call_args
        assert call_args[0][0].get("due_date") == "2025-01-01"

    def test_get_promises_returns_list(self, manager, mock_supabase):
        """約束一覧を取得できる"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "1", "user_id": "test_user_123", "content": "映画", "status": "pending", "created_at": "2025-01-01"},
                {"id": "2", "user_id": "test_user_123", "content": "食事", "status": "pending", "created_at": "2025-01-02"},
            ]
        )

        from orchestration.memory.structured import Promise
        promises = manager.get_promises()

        assert len(promises) == 2
        assert all(isinstance(p, Promise) for p in promises)

    def test_get_promises_filter_by_status(self, manager, mock_supabase):
        """ステータスでフィルタできる"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[{"id": "1", "status": "fulfilled", "content": "映画", "created_at": "2025-01-01"}]
        )

        promises = manager.get_promises(status="fulfilled")

        # eqが2回呼ばれる（user_idとstatus）
        assert mock_supabase.table.return_value.select.return_value.eq.return_value.eq.called

    def test_update_promise_status(self, manager, mock_supabase):
        """約束のステータスを更新できる"""
        mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[{}])

        result = manager.update_promise_status("promise_1", "fulfilled")

        assert result is True
        mock_supabase.table.return_value.update.assert_called()


class TestBoundary:
    """境界線（NG）のテスト"""

    def test_save_boundary(self, manager, mock_supabase):
        """NGを保存できる"""
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "boundary_1", "content": "元カノの話はしないで"}]
        )

        result = manager.save_boundary("元カノの話はしないで", category="topic")

        assert result is not None
        mock_supabase.table.assert_called_with("boundaries")

    def test_save_boundary_with_severity(self, manager, mock_supabase):
        """重要度付きでNGを保存できる"""
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])

        manager.save_boundary("急に電話しないで", category="action", severity=0.8)

        call_args = mock_supabase.table.return_value.insert.call_args
        assert call_args[0][0].get("severity") == 0.8

    def test_get_boundaries_returns_list(self, manager, mock_supabase):
        """NG一覧を取得できる"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "1", "user_id": "test_user_123", "content": "元カノの話", "category": "topic", "severity": 0.9, "created_at": "2025-01-01"},
            ]
        )

        from orchestration.memory.structured import Boundary
        boundaries = manager.get_boundaries()

        assert len(boundaries) == 1
        assert isinstance(boundaries[0], Boundary)
        assert boundaries[0].category == "topic"

    def test_check_boundary_matches(self, manager, mock_supabase):
        """テキストがNGに該当するかチェック"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "1", "content": "元カノ", "category": "topic", "severity": 0.9, "created_at": "2025-01-01"},
            ]
        )

        result = manager.check_boundary("元カノとはどうなったの？")

        assert result is not None
        assert "元カノ" in result.content

    def test_check_boundary_no_match(self, manager, mock_supabase):
        """NGに該当しない場合はNone"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "1", "content": "元カノ", "category": "topic", "severity": 0.9, "created_at": "2025-01-01"},
            ]
        )

        result = manager.check_boundary("今日の天気はどう？")

        assert result is None


class TestIntegrationWithClassifier:
    """発話分類との連携テスト"""

    def test_process_profile_classification(self, manager, mock_supabase):
        """profile分類の結果からプロフィールを更新"""
        mock_supabase.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[{}])

        from orchestration.utterance_classifier import ClassificationResult, UtteranceCategory

        classification = ClassificationResult(
            category=UtteranceCategory.PROFILE,
            confidence=0.9,
            extracted_info={"name": "花子"},
            reasoning=""
        )

        manager.process_classification(classification)

        # save_profileが呼ばれている
        mock_supabase.table.assert_called()

    def test_process_promise_classification(self, manager, mock_supabase):
        """promise分類の結果から約束を保存"""
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])

        from orchestration.utterance_classifier import ClassificationResult, UtteranceCategory

        classification = ClassificationResult(
            category=UtteranceCategory.PROMISE,
            confidence=0.8,
            extracted_info={"future_plan": "来週ディズニーに行く"},
            reasoning=""
        )

        manager.process_classification(classification)

        mock_supabase.table.assert_called_with("promises")

    def test_process_boundary_classification(self, manager, mock_supabase):
        """boundary分類の結果からNGを保存"""
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])

        from orchestration.utterance_classifier import ClassificationResult, UtteranceCategory

        classification = ClassificationResult(
            category=UtteranceCategory.BOUNDARY,
            confidence=0.85,
            extracted_info={"ng_topic": "仕事の話"},
            reasoning=""
        )

        manager.process_classification(classification)

        mock_supabase.table.assert_called_with("boundaries")

    def test_skip_low_confidence_classification(self, manager, mock_supabase):
        """confidence低い場合はスキップ"""
        from orchestration.utterance_classifier import ClassificationResult, UtteranceCategory

        classification = ClassificationResult(
            category=UtteranceCategory.PROFILE,
            confidence=0.3,  # 低い
            extracted_info={"name": "花子"},
            reasoning=""
        )

        manager.process_classification(classification)

        # 何も保存されない
        mock_supabase.table.return_value.upsert.assert_not_called()
        mock_supabase.table.return_value.insert.assert_not_called()
