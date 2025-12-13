# 作業ログ

Claude Code / Codex 共通の作業履歴。作業後は必ず追記すること。

---

## 2025-12-04
### プロジェクト初期構築
- ExecPlan（実装計画書）初版作成
- Pythonプロジェクト骨組み作成（ディレクトリ構成、requirements.txt、README.md）
- 技術仕様書（youkenn.md）作成：Observer-Actorモデルのアーキテクチャ設計

### データベース・ストレージ層
- SQLite永続化層（storage.py）実装
- user_states テーブル：ユーザー状態のJSON保存
- chat_logs テーブル：会話履歴の保存
- CRUD関数実装（fetch_state, update_state, fetch_history, append_log）

### コアモジュール実装
- models.py：dataclassesでUserState, ScenarioState, Biometrics, ObservationResult定義
- Observer（observer.py）実装
  - キーワードベースの感情分析
  - mood/affection/energy/trust の増減ロジック
  - 長期記憶（ファクト抽出）機能
  - シナリオフラグ管理
- Actor（actor.py）実装
  - mood/energy/affectionに応じた口調テンプレート
  - シーン情報や長期記憶を反映した返答生成
- Orchestrator（orchestrator.py）実装
  - process_chat_turn関数：状態読込→Observer更新→DB保存→Actor生成→ログ保存

### エントリポイント
- main.py作成：CLI/HTTP両対応
  - CLI：標準入力で対話、--userオプションでユーザー指定
  - FastAPI：/chat POSTエンドポイント

### LLM統合
- llm_client.py：OpenAI APIラッパー実装
- LLM優先でObserve/Act、未設定時はルールベースへフォールバック
- .env.example追加、設定ローダー整備

## 2025-12-05
### プロンプト外部化
- orchestration/prompts/ディレクトリ作成
- actor_system.txt：Actor用システムプロンプト
- observer_system.txt：Observer用システムプロンプト
- prompt_loader.py：プロンプト読み込みユーティリティ
- 非エンジニアでも編集可能な構成に

### マルチLLMプロバイダー対応
- Actor：Grok(xAI)をデフォルトに変更
- Observer：OpenAI継続
- 環境変数でprovider/model切替可能に
  - OBSERVER_PROVIDER, OBSERVER_MODEL
  - ACTOR_PROVIDER, ACTOR_MODEL

### Web UI追加
- FastAPI直下（/）にWeb UIを追加
- 日本語表記の会話インターフェース
- ステート表示（mood/energy/affection/trust）
- 会話ログ表示
- JSON形式での詳細状態確認

## 2025-12-06
### キャラクター設定
- orchestration/data/idol_story.json：キャラクター情報・ストーリー設定
- critic_system.txt：Critic用システムプロンプト

## 2025-12-11〜12
### 拡張モジュール
- memory/ディレクトリ：メモリ管理拡張
- agents/ディレクトリ：エージェント拡張
- rules/ディレクトリ：ルールエンジン
  - rule_types.py, rule_registry.py
  - data/rules/behavior_rules.json
- dialogue/ディレクトリ：対話管理
- game_state/ディレクトリ：ゲーム状態管理
- graph/ディレクトリ：グラフ構造
- validation/ディレクトリ：バリデーション
- session.py：セッション管理
- agent_logger.py：エージェントログ機能
- verify_memory.py：メモリ検証ツール
- settings.py：設定管理
- critic.py：Critic（評価）機能

### UI素材
- ui/ディレクトリ：キャラクター画像追加
  - yumeka_normal.png（通常表情）
  - yumeka_happy.png（喜び表情）
  - yumeka_angry.png（怒り表情）

## 2025-12-13
### プロジェクト構成整理 [Claude]
- PROJECT.md 作成：共通ルール・方針を集約
- WORKLOG.md 作成：作業ログを統一
- PLAN.md 作成：計画・進捗を統一
- claude.md / AGENTS.md を「働き方」のみに整理
