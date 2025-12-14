"""MemoryCompressorのテスト（TDD）

Issue #004: 定期圧縮（週次要約＋スコア減衰）
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


@pytest.fixture
def mock_supabase():
    """Supabaseクライアントのモック"""
    with patch("orchestration.memory.compressor.get_supabase") as mock:
        client = MagicMock()
        mock.return_value = client
        yield client


@pytest.fixture
def mock_llm():
    """LLMクライアントのモック"""
    mock = MagicMock()
    mock.json_chat.return_value = {
        "summary": "今週はユーザーと映画について話し、来週の予定を立てた。"
    }
    return mock


@pytest.fixture
def compressor(mock_supabase, mock_llm):
    """MemoryCompressorのインスタンス"""
    from orchestration.memory.compressor import MemoryCompressor
    comp = MemoryCompressor(user_id="test_user_123")
    comp._llm_client = mock_llm  # 直接モックを注入
    return comp


class TestWeeklySummary:
    """週次要約のテスト"""

    def test_create_weekly_summary_success(self, compressor, mock_supabase, mock_llm):
        """週次要約が生成できる"""
        # 今週の中期記憶をモック
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)

        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "1", "summary": "映画の話をした", "importance": 0.7, "created_at": now.isoformat()},
                {"id": "2", "summary": "来週の予定を立てた", "importance": 0.6, "created_at": now.isoformat()},
            ]
        )
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(
            data=[{"id": "weekly_1"}]
        )

        result = compressor.create_weekly_summary()

        assert result is not None
        assert "映画" in result or "今週" in result
        mock_llm.json_chat.assert_called_once()

    def test_create_weekly_summary_no_memories(self, compressor, mock_supabase):
        """中期記憶がない場合はNone"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.execute.return_value = MagicMock(
            data=[]
        )

        result = compressor.create_weekly_summary()

        assert result is None

    def test_weekly_summary_saved_to_db(self, compressor, mock_supabase, mock_llm):
        """週次要約がDBに保存される"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.execute.return_value = MagicMock(
            data=[{"id": "1", "summary": "テスト", "importance": 0.5, "created_at": datetime.utcnow().isoformat()}]
        )
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])

        compressor.create_weekly_summary()

        # weekly_summariesテーブルにinsertされる
        calls = [call for call in mock_supabase.table.call_args_list if "weekly" in str(call)]
        assert len(calls) > 0


class TestDecayMemories:
    """スコア減衰のテスト"""

    def test_decay_old_memories(self, compressor, mock_supabase):
        """古い記憶の重要度が減衰する"""
        old_date = (datetime.utcnow() - timedelta(days=35)).isoformat()
        mock_supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "1", "importance": 0.5},
                {"id": "2", "importance": 0.3},
            ]
        )
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        count = compressor.decay_memories()

        assert count == 2

    def test_decay_deletes_low_importance(self, compressor, mock_supabase):
        """重要度が閾値以下になったら削除"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "1", "importance": 0.05},  # 閾値以下
            ]
        )
        mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

        compressor.decay_memories()

        # deleteが呼ばれる
        mock_supabase.table.return_value.delete.assert_called()

    def test_no_old_memories(self, compressor, mock_supabase):
        """古い記憶がない場合は0"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
            data=[]
        )

        count = compressor.decay_memories()

        assert count == 0


class TestArchive:
    """アーカイブのテスト"""

    def test_archive_low_importance(self, compressor, mock_supabase):
        """低重要度記憶がアーカイブされる"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
            data=[
                {"id": "1", "user_id": "test_user_123", "content": "古い記憶", "importance": 0.08},
            ]
        )
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])
        mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

        count = compressor.archive_low_importance(threshold=0.1)

        assert count == 1

    def test_archive_moves_to_archive_table(self, compressor, mock_supabase):
        """アーカイブテーブルに移動される"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
            data=[{"id": "1", "user_id": "test_user_123", "content": "古い記憶", "importance": 0.05}]
        )
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])
        mock_supabase.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

        compressor.archive_low_importance()

        # archived_memoriesにinsert
        insert_calls = mock_supabase.table.return_value.insert.call_args_list
        assert len(insert_calls) > 0

    def test_no_low_importance_memories(self, compressor, mock_supabase):
        """低重要度記憶がない場合は0"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
            data=[]
        )

        count = compressor.archive_low_importance()

        assert count == 0


class TestRunMaintenance:
    """一括メンテナンスのテスト"""

    def test_run_maintenance_returns_stats(self, compressor, mock_supabase, mock_llm):
        """メンテナンス結果の統計が返る"""
        # モック設定
        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.execute.return_value = MagicMock(data=[])
        mock_supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(data=[])

        result = compressor.run_maintenance()

        assert "weekly_summary" in result
        assert "decayed_count" in result
        assert "archived_count" in result

    def test_run_maintenance_executes_all(self, compressor, mock_supabase, mock_llm):
        """全てのメンテナンス処理が実行される"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.execute.return_value = MagicMock(
            data=[{"id": "1", "summary": "テスト", "importance": 0.5, "created_at": datetime.utcnow().isoformat()}]
        )
        mock_supabase.table.return_value.select.return_value.eq.return_value.lt.return_value.execute.return_value = MagicMock(
            data=[{"id": "2", "importance": 0.5}]
        )
        mock_supabase.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{}])
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        result = compressor.run_maintenance()

        # 各処理が実行された
        assert result["decayed_count"] >= 0
        assert result["archived_count"] >= 0


class TestEdgeCases:
    """エッジケースのテスト"""

    def test_db_error_handled(self, compressor, mock_supabase):
        """DBエラーが適切に処理される"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.execute.side_effect = Exception("DB Error")

        result = compressor.create_weekly_summary()

        assert result is None

    def test_llm_error_handled(self, compressor, mock_supabase, mock_llm):
        """LLMエラーが適切に処理される"""
        mock_supabase.table.return_value.select.return_value.eq.return_value.gte.return_value.order.return_value.execute.return_value = MagicMock(
            data=[{"id": "1", "summary": "テスト", "importance": 0.5, "created_at": datetime.utcnow().isoformat()}]
        )
        mock_llm.json_chat.side_effect = Exception("LLM Error")

        result = compressor.create_weekly_summary()

        assert result is None
