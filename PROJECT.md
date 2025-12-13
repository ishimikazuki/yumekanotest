# プロジェクト共通ルール

このファイルはClaude Code / Codex 共通の方針です。

## プロジェクト概要
ステート駆動型オーケストレーションBot - LLMを用いた対話システムで「長期記憶」「感情の揺らぎ」「シナリオ進行」を実現する。

## 技術スタック
- Python（FastAPI / 標準ライブラリ）
- SQLite（永続化）
- LLM: OpenAI（Observer）/ xAI Grok（Actor）

## 言語・コミュニケーション
- 日本語で回答する
- コメントやコミットメッセージも日本語で書く
- 説明は初心者にもわかりやすく
- エラーは詳しく説明する

## コーディング規約
- dataclassesベースでモデル定義（FastAPI非依存でもCLI動作可能に）
- プロンプトは `orchestration/prompts/*.txt` に外部化
- 設定は環境変数で管理（.env）

## 作業ルール
- 作業内容は `WORKLOG.md` に記録する
- 計画・進捗は `PLAN.md` に記録する
- コミットメッセージは変更内容がわかるように具体的に書く

## ディレクトリ構成
```
orchestrationbot/
├── main.py                 # CLI / FastAPI エントリポイント
├── orchestration/          # ロジック本体
│   ├── models.py           # ステートデータクラス
│   ├── storage.py          # SQLite永続化
│   ├── observer.py         # 状態更新
│   ├── actor.py            # 発話生成
│   ├── orchestrator.py     # パイプライン結合
│   ├── llm_client.py       # LLMクライアント
│   └── prompts/            # システムプロンプト
├── data/                   # データファイル
└── ui/                     # UI素材
```

## 参照ドキュメント
- `youkenn.md` - 技術仕様書（Observer-Actorモデル設計）
- `PLAN.md` - 現在の実装計画
- `WORKLOG.md` - 作業履歴
