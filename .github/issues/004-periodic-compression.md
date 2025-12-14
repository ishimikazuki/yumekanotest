# Issue #004: 定期圧縮（週次要約＋スコア減衰）

**Status**: 🟢 Closed
**Created**: 2025-12-14
**Labels**: `feature`, `memory`, `TDD`

## 概要
長期記憶の定期的なメンテナンス機能を実装する。
- 週次要約: 中期記憶を週単位で要約
- スコア減衰: 古いエピソードの重要度を減衰
- アーカイブ: 重要度が閾値以下のエピソードをアーカイブ

## 背景
現在の実装:
- `decay_old_memories()`: 30日未アクセス記憶の減衰 ✅
- 週次要約: 未実装
- アーカイブ処理: 未実装

## 実装内容

### 1. MemoryCompressor クラス
```python
class MemoryCompressor:
    def __init__(self, user_id: str):
        ...

    def create_weekly_summary(self) -> Optional[str]:
        """今週の中期記憶を要約"""
        ...

    def decay_memories(self) -> int:
        """古い記憶の重要度を減衰"""
        ...

    def archive_low_importance(self, threshold: float = 0.1) -> int:
        """低重要度記憶をアーカイブ"""
        ...

    def run_maintenance(self) -> Dict:
        """定期メンテナンスを実行"""
        ...
```

### 2. 週次要約
- 今週の中期記憶（要約）を集約
- LLMで全体要約を生成
- `weekly_summaries` テーブルに保存

### 3. スコア減衰
- 既存: 30日未アクセスで0.1減衰
- 追加: 減衰後に閾値（0.1）以下なら削除対象

### 4. アーカイブ
- 重要度が閾値以下の記憶を `archived_memories` に移動
- 元テーブルからは削除

## 受け入れ基準
- [x] テストが全て通る（13テスト通過）
- [x] 週次要約が生成できる
- [x] スコア減衰が動作する
- [x] 低重要度記憶がアーカイブされる
- [x] run_maintenance()で一括実行できる

## 関連
- Issue #001: 発話分類器 ✅
- Issue #002: 構造化メモリ ✅
- Issue #003: 応答生成の注入順序 ✅
