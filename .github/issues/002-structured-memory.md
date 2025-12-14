# Issue #002: 構造化メモリ（プロフィール/約束/NG）の実装

**Status**: 🟢 Closed
**Created**: 2025-12-14
**Labels**: `feature`, `memory`, `TDD`

## 概要
ユーザーの重要な情報を構造化して保存・検索できるメモリシステムを実装する。

## 背景
現在の長期メモリは `fact/emotion/preference/event` の4タイプのみで、プロフィール・約束・NGなどの構造化データに対応していない。

## 実装内容

### 1. 新しいメモリタイプ
- `user_profile`: ユーザーの基本情報（名前、年齢、職業、趣味など）
- `promise`: 約束・予定（「今度〇〇しよう」など）
- `boundary`: NG・境界線（「〇〇しないで」「〇〇の話は嫌」など）

### 2. データ構造
```python
@dataclass
class UserProfile:
    user_id: str
    name: Optional[str]
    age: Optional[int]
    occupation: Optional[str]
    location: Optional[str]
    birthday: Optional[str]
    hobbies: List[str]
    preferences: Dict[str, str]  # {"food": "ラーメン", "color": "青"}

@dataclass
class Promise:
    id: str
    user_id: str
    content: str
    created_at: str
    due_date: Optional[str]
    status: str  # "pending", "fulfilled", "broken"

@dataclass
class Boundary:
    id: str
    user_id: str
    content: str
    category: str  # "topic", "action", "time"
    severity: float  # 0.0-1.0
    created_at: str
```

### 3. API
- `StructuredMemoryManager.save_profile(field, value)`
- `StructuredMemoryManager.get_profile() -> UserProfile`
- `StructuredMemoryManager.save_promise(content, due_date=None)`
- `StructuredMemoryManager.get_promises(status=None) -> List[Promise]`
- `StructuredMemoryManager.update_promise_status(promise_id, status)`
- `StructuredMemoryManager.save_boundary(content, category, severity=0.5)`
- `StructuredMemoryManager.get_boundaries() -> List[Boundary]`
- `StructuredMemoryManager.check_boundary(text) -> Optional[Boundary]`

### 4. 発話分類との連携
`UtteranceClassifier` の結果に基づいて自動保存:
- `profile` → UserProfile更新
- `promise` → Promise追加
- `boundary` → Boundary追加

## 受け入れ基準
- [x] テストが全て通る（19テスト通過）
- [x] プロフィール情報の保存・取得ができる
- [x] 約束の保存・取得・ステータス更新ができる
- [x] NGの保存・取得ができる
- [x] boundary違反チェックが動作する

## 関連
- Issue #001: 発話分類器（UtteranceClassifier）✅ 完了
