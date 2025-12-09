# ステート駆動型オーケストレーションBot実装プラン（ExecPlan）

このドキュメントは living document です。.agent/PLANS.md の要件に従い、進捗・判断・発見を随時更新します。

## Purpose / Big Picture

LLM なしでも動作する「Observer（状態更新）＋Actor（演技発話）」構造の最小実装を用意し、1 ユーザーとの対話を通じて「長期記憶」「感情の揺らぎ」「シナリオ進行」を確認できる CLI/HTTP 両対応の Python プロトタイプを作る。ユーザーは `python main.py`（CLI）または `uvicorn main:app`（HTTP）を実行し、メッセージを送ると最新ステートに基づいた返答を得られる。

- [x] (2025-12-04T16:31Z) ExecPlan 初版作成。
- [x] (2025-12-04T16:35Z) Python プロジェクト骨組み作成（ディレクトリ、requirements、README 追加）。
- [x] (2025-12-04T16:35Z) ストレージ層実装（SQLite 永続化、state/history CRUD）。
- [x] (2025-12-04T16:35Z) Observer 実装（キーワードで biometrics/flags 更新、ファクト抽出）。
- [x] (2025-12-04T16:35Z) Actor 実装（mood/energy/affection に応じた口調生成）。
- [x] (2025-12-04T16:35Z) Orchestrator 実装（process_chat_turn、ログ保存）。
- [x] (2025-12-04T16:35Z) HTTP/CLI エントリ追加（FastAPI は任意依存、CLI は標準ライブラリのみ）。
- [x] (2025-12-04T16:45Z) LLM 統合（OpenAI ラッパー、LLM優先で観測・発話、未設定時はフォールバック）。
- [x] (2025-12-04T16:45Z) .env.example 追加・設定ローダー整備。
- [x] (2025-12-05T15:20Z) Actor/Observer のシステムプロンプトを外部テキスト化し、手書き編集を容易化。
- [x] (2025-12-05T16:55Z) Actor を Grok(xAI) 優先に切替可能にし、provider/model を環境変数化。
- [ ] 簡易テスト・デモシナリオ実行（completed: 単発 smoke; remaining: CLI 3 往復・UI 操作と DB 確認）。
- [ ] Outcomes/Retrospective 反映・最終整理。

## Surprises & Discoveries

- （未記載）

## Decision Log
- Decision: モデル定義を dataclasses ベースで実装し、FastAPI 依存が無い環境でも CLI を動作させる。  
  Rationale: ネットワーク制限下でも動作確認できるようにするため。  
  Date/Author: 2025-12-04T16:35Z / assistant
- Decision: LLM は OpenAI クライアントを optional 依存とし、APIキー未設定時はルールベースへフォールバックする実装にする。  
  Rationale: オフライン環境での検証を担保しつつ、本実装（LLM駆動）も即切り替え可能にするため。  
  Date/Author: 2025-12-04T16:45Z / assistant
- Decision: プロンプト文面を `orchestration/prompts/*.txt` に分離し、コードから読み込む形に変更する。  
  Rationale: 非エンジニアでもテキストを手書き修正しやすくし、実行時は欠損時にデフォルトへ自動フォールバックさせるため。  
  Date/Author: 2025-12-05T15:20Z / assistant
- Decision: Actor は Grok(xAI) をデフォルトとし、provider/model を環境変数で切替可能にした（Observer は OpenAI 継続）。  
  Rationale: 要件「Actor: grok-4-fast」を満たすため、xAI の OpenAI 互換エンドポイントをサポート。  
  Date/Author: 2025-12-05T16:55Z / assistant
- Decision: Web UI を FastAPI 直下 `/` に追加し、日本語表記で会話・ステート・履歴を同一画面に表示する構成にした。  
  Rationale: 要件の「UI 上で会話」「DB表示」を満たすため。  
  Date/Author: 2025-12-05T17:10Z / assistant

## Outcomes & Retrospective

- （未記載）

## Context and Orientation

リポジトリには仕様書 `youkenn.md` のみが存在する。ここでは Python 製のミニプロトタイプを追加する。コアは標準ライブラリ（dataclasses, sqlite3）で動き、HTTP API を使う場合のみ `fastapi`/`uvicorn`/`pydantic` を追加インストールする。ステートは `data/bot.db`（SQLite）に永続化し、JSON 文字列で保持する。

## Plan of Work

1. プロジェクトセットアップ  
   - `python -m venv .venv`、`source .venv/bin/activate`。  
   - `requirements.txt` に `fastapi`, `uvicorn[standard]`, `pydantic` を記載（標準ライブラリのみで CLI 可）。  
   - パッケージ構成: `orchestration/` にロジックを配置、`main.py` は CLI & FastAPI エントリ。

2. ストレージ層 (`orchestration/storage.py`)  
   - SQLite を開き、`user_states(user_id TEXT PRIMARY KEY, state_json TEXT, updated_at TEXT)` と `chat_logs(id INTEGER PRIMARY KEY, user_id TEXT, role TEXT, content TEXT, created_at TEXT)` を用意。  
   - CRUD 関数: `fetch_state(user_id) -> dict | None`, `update_state(user_id, state_dict)`, `fetch_history(user_id, limit=10) -> list`, `append_log(user_id, role, content)`。

3. ドメインモデル (`orchestration/models.py`)  
   - dataclasses で `UserState`, `ScenarioState`, `Biometrics`, `ObservationResult` を定義（外部依存なし）。  
   - デフォルト初期値（mood=0, energy=70, affection=20, trust=10, phase/scene 初期化）を提供。

4. Observer (`orchestration/observer.py`)  
   - 入力: `user_message(str)`, `state(UserState)`, `history(list[dict])`。  
   - キーワードベースの簡易感情分析（好意/攻撃/疲労ワード）で mood/affection/energy/trust を増減。  
   - `long_term_memories` へ「〜が好き/苦手」「約束」などの新規ファクト抽出（正規表現ベース）。  
   - `scenario.flags` と `current_phase/scene` を簡易遷移（trust が 50 超で `trigger_event_confession` を true 等）。  
   - 出力: 更新後の `UserState` と任意 `instruction_override`（例: 気まずい時は話題転換）。

5. Actor (`orchestration/actor.py`)  
   - 入力: `user_message`, `history`, `state`, `instruction_override`。  
   - mood/energy/affection に応じた口調テンプレート（優しい/素っ気ない/眠そう等）を選択し、シーン名や long_term_memories の一部を混ぜた返答を組み立てる。  
   - override があれば語尾や話題を調整。

6. オーケストレーター (`orchestration/orchestrator.py`)  
   - 関数 `process_chat_turn(user_id, user_message)` を実装。  
   - フロー: ステート/履歴読み込み → observer 更新 → DB 保存 → actor 生成 → ログ保存 → 返信返却。

7. エントリポイント (`main.py`)  
   - CLI: 標準入力で対話、`--user <id>` でユーザー指定、`exit` で終了。  
   - FastAPI: `/chat` POST {user_id, message} → {reply, state}. FastAPI 未インストール時は CLI のみ動作するよう try/except インポート。

8. 検証  
   - CLI で 3 往復実行し、`data/bot.db` に state/log が更新されることを確認。  
   - （依存インストール済みなら）`uvicorn main:app --reload` を起動し、`curl -X POST localhost:8000/chat -d '{"user_id":"u1","message":"おはよう"}'` で応答を確認。

9. 文書化  
   - `README.md` に使い方・依存・想定動作を簡潔に記載。  
   - ExecPlan の Progress/Decision/Surprises/Outcomes を更新。

## Concrete Steps

- 作業ディレクトリ: リポジトリ直下。  
- 代表コマンド例（依存導入後）  
  - `python -m venv .venv`  
  - `source .venv/bin/activate`  
  - `pip install -r requirements.txt`  
  - CLI: `python main.py --user demo`  
  - API: `uvicorn main:app --reload`  
- 期待ログ（例）  
  - 入力: 「おはよう」 → 応答に現在の mood/scene 反映（例: 「まだ眠いけど…」）  
  - `data/bot.db` の `user_states.state_json` に mood/affection が更新され、`chat_logs` に対話が追記される。

## Validation and Acceptance

CLI で 3 往復時、trust が上昇し scenario.flags のいずれかが true になることを確認する。API が起動できる場合、POST `/chat` が 200 を返し JSON に `reply` と最新 `state` を含むこと。テストコマンドは未整備のため、手動検証を acceptance とする。

## Idempotence and Recovery

同じメッセージを送ってもステートは決定的に更新される（加算はクリップ済み）。DB ファイル `data/bot.db` を削除すれば初期状態に戻せる。初期化用関数を `storage.py` に用意して再実行可能にする。

## Artifacts and Notes

実装後、主要ファイルと簡易ログ例をここに追記予定。

## Interfaces and Dependencies

主要関数の最終形（予定）:

    storage.fetch_state(user_id: str) -> UserState | None
    storage.update_state(user_id: str, state: UserState) -> None
    storage.fetch_history(user_id: str, limit: int = 10) -> list[dict]
    storage.append_log(user_id: str, role: str, content: str) -> None

    observer.update_state(user_message: str, state: UserState, history: list[dict]) -> ObservationResult

    actor.generate_reply(user_message: str, history: list[dict], state: UserState, instruction_override: str | None) -> str

    orchestrator.process_chat_turn(user_id: str, user_message: str) -> dict(reply: str, state: UserState)
