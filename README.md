# ステート駆動型オーケストレーション Bot（プロトタイプ）

## できること
- Observer（状態更新）と Actor（演技発話）の 2 段構成で、会話ごとに機嫌や信頼度などを更新。
- SQLite (`data/bot.db`) に長期記憶・短期履歴を保存。
- LLM API（OpenAI）設定時はステート更新・発話生成を LLM で行い、未設定でもローカルルールで動作。
- CLI 対話は標準ライブラリのみで動作。FastAPI/uvicorn を入れれば HTTP API も利用可能。

## 使い方
### 0) 環境変数
`.env.example` をコピーして `.env` を作成し、以下を設定してください。
- `OPENAI_API_KEY` … Observer 用（OpenAI）
- `XAI_API_KEY` … Actor 用（Grok / xAI）
- `OBSERVER_MODEL`（既定: gpt-4o-mini）
- `ACTOR_MODEL`（既定: grok-4-fast）
- `OBSERVER_PROVIDER`=`openai` / `ACTOR_PROVIDER`=`xai`（既定）
⚠️ 本MVPは LLM 必須です。`OPENAI_API_KEY`（Observer）と `XAI_API_KEY`（Actor）が未設定または無効な場合、エラーを返します（テンプレートにはフォールバックしません）。

### 1) 依存インストール（任意）
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) CLI で試す
```
python main.py --user demo
```
`exit` で終了。発話に応じて `data/bot.db` にステート・履歴が記録されます。

### 3) HTTP API（依存インストール済みの場合）
```
python main.py --serve
```
別ターミナルから:
```
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"demo","message":"おはよう"}'
```

### 4) Web UI（日本語表記）
`python main.py --serve` 実行後、ブラウザで `http://localhost:8000/` を開くと UI から会話できます。  
・左でユーザーIDと発話を入力→送信  
・右ペインでステート（mood/energy/affection/trust 等）と JSON を即時表示  
・会話ログも UI 上で確認できます（同一 DB を参照）

## 構成
- `main.py` … CLI / FastAPI エントリポイント
- `orchestration/` … ロジック本体
  - `models.py` … ステートデータクラス
  - `storage.py` … SQLite 永続化
  - `observer.py` … 状態更新ルール
  - `actor.py` … 発話生成
  - `orchestrator.py` … パイプライン結合
  - `prompts/actor_system.txt`, `prompts/observer_system.txt` … LLM 用システムプロンプト（手書き編集可）

## プロンプトを編集したいとき
`orchestration/prompts/*.txt` を直接書き換えてください。空ファイルや削除時はコード内のデフォルト文面に自動フォールバックします。

## メモ
- FastAPI が未インストールでも CLI は動作します。
- ステート初期化は `orchestration.storage.reset_user(<id>)` を呼び出すか `data/bot.db` を削除してください。
