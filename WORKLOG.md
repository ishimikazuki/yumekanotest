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

## 2025-12-14
### 構造化メモリ実装 [Claude] (#002)
- UserProfile: 名前、年齢、職業、趣味などを構造化管理
- Promise: 約束の保存・取得・ステータス更新
- Boundary: NG/境界線の保存・違反チェック
- 発話分類との連携: ClassificationResultから自動保存
- TDD: 19テスト作成・全通過

### 応答生成の注入順序改善 [Claude] (#003)
- build_actor_prompt_v2() を追加
- 注入順序: Persona → UserProfile → 約束/NG → エピソード → 短期 → 発話
- Boundary警告: 高重要度NGには⚠️マークと警告文を追加
- 後方互換性: 既存のbuild_actor_prompt()は維持
- TDD: 12テスト作成・全通過

### 定期圧縮機能 [Claude] (#004)
- MemoryCompressorクラスを実装
  - create_weekly_summary(): 週次要約の生成
  - decay_memories(): 古い記憶のスコア減衰
  - archive_low_importance(): 低重要度記憶のアーカイブ
  - run_maintenance(): 一括メンテナンス実行
- TDD: 13テスト作成・全通過

### テスト修正・メモリ保存フック追加 [Codex]
- orchestrator のレガシーフローでベクトル記憶保存を追加し、`memory_system` をモックしやすい形に変更。
- `orchestration.memory.vector_store` を導入し、インポート経路を整理。
- `tests/test_orchestrator.py` のパッチ対象に合わせて呼び出しを反映し、pytest が全件パスすることを確認。

### Supabase 本番用セットアップ準備 [Codex]
- `.env.example` に `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `DRY_RUN` を追加し、本番で記憶保存を有効化するための環境変数を明示。
- `requirements.txt` に `supabase` を追加。
- Supabase で必要なテーブル・RPC・拡張をまとめた `data/supabase_schema.sql` を追加（short/mid/long term memory と match_long_term_memory 関数、pgvector インデックス）。

## 2025-12-15
### Vercel初期設定 [Claude]
- `api/index.py` 作成: Vercel Python Functionエントリポイント
- `vercel.json` 作成: ビルド設定、ルーティング、環境変数
- APIルーティング修正（/api パス対応）
- root_path設定とルーティング簡素化

## 2025-12-17
### Vercelデプロイ準備 [Claude]
- コードベース整理とコミット
- vercel.json静的ファイルパターン修正（`ui/**/*`）
- 自動デプロイトリガーテスト

## 2025-12-18
### Vercelデプロイ設定 [Claude]
- vercel.json の修正（静的ファイルパターン `ui/**/*`）
- 環境変数シークレット参照を削除（ダッシュボードで設定する方式に変更）
- Vercel CLIでのデプロイ確認

### GitHub App連携修正 [Claude]
- GitHub Appの権限設定を修正（リポジトリアクセス権限の追加）
- 自動デプロイがトリガーされるように設定

### Vercel軽量API版作成 [Claude]
- Vercelの250MBサイズ制限に対応
- chromadb/langgraphを除外した軽量版 `api/index.py` を作成
- `api/requirements.txt` を追加（openai, python-dotenv, httpx, supabase, fastapi, pydantic）
- OpenAI直接呼び出しによる簡易チャット機能

### Vercel API修正（フル版統合）
- OpenAI接続修正: 明示的なbase_url設定とAPIキーチェック
- actor_system.txtプロンプト読み込み対応
- emotion keys修正（P/A/D → pleasure/arousal/dominance）
- logs/session管理のエラーハンドリング改善
- orchestrationモジュール完全統合版を作成
  - Observer-Actor-Criticループ対応
  - ChromaDB条件付きインポート（Vercel環境スキップ）
  - /tmp をSQLiteパスとして使用（Vercelサーバーレス対応）

### 動作確認 [Claude]
- UI: https://yumekanotest-ten.vercel.app/ ✅
- API: https://yumekanotest-ten.vercel.app/api/dryrun ✅
- 自動デプロイ: GitHubプッシュでトリガー確認 ✅

## 2025-12-19
### CLAUDE.md改善 [Claude]
- 「必須アクション」セクションを追加（作業開始時・完了時のチェックリスト）
- TodoWriteに「WORKLOG.md更新」を必ず含めるルールを明記
- 作業完了時にCLAUDE.mdを再確認するよう注意書き追加

### WORKLOG.md補完 [Claude]
- 2025-12-14〜12-18の未記載作業をgit履歴から復元
- 構造化メモリ(#002)、注入順序改善(#003)、定期圧縮(#004)を追記
- Vercel初期設定〜フル版統合までの全作業を追記
