# Issue #003: 応答生成の注入順序を改善

**Status**: 🟢 Closed
**Created**: 2025-12-14
**Labels**: `feature`, `prompt`, `TDD`

## 概要
Actor（応答生成）のプロンプトに、構造化メモリ（プロフィール/約束/NG）を適切な順序で注入する。

## 背景
現在の `prompt_builder.py` は以下の順序:
1. 状態
2. 演技指針
3. 長期記憶
4. ルール
5. 会話履歴
6. ユーザー発話

目標の順序:
1. **Persona**（キャラクター設定）
2. **UserProfile**（ユーザー情報）
3. **約束/NG**（守るべきこと）
4. **検索エピソード**（Vector検索結果）
5. **短期記憶**（直近会話）
6. **ユーザー発話**

## 実装内容

### 1. PromptBuilderの改修
```python
def build_actor_prompt(
    self,
    user_message: str,
    history: List[Dict],
    state: UserState,
    user_profile: Optional[UserProfile] = None,
    promises: Optional[List[Promise]] = None,
    boundaries: Optional[List[Boundary]] = None,
    retrieved_episodes: Optional[List[str]] = None,
    ...
) -> str:
```

### 2. 注入テンプレート
```
## キャラクター設定（Persona）
{persona}

## ユーザー情報（UserProfile）
- 名前: {name}
- 趣味: {hobbies}
...

## 守るべき約束
- {promise1}
- {promise2}

## 触れてはいけない話題（NG）
- {boundary1}
- {boundary2}

## 関連エピソード
- {episode1}
- {episode2}

## 直近の会話
{short_term_history}

## ユーザーの発言
{user_message}
```

### 3. Boundary違反時の警告
Actorへの指示に「この話題には触れないでください」を追加。

## 受け入れ基準
- [x] テストが全て通る（12テスト通過）
- [x] Personaが最初に注入される
- [x] UserProfileが2番目に注入される
- [x] 約束/NGが3番目に注入される
- [x] Vector検索結果が4番目に注入される
- [x] 短期記憶が5番目に注入される
- [x] Boundary違反時に警告が含まれる

## 関連
- Issue #001: 発話分類器 ✅
- Issue #002: 構造化メモリ ✅
