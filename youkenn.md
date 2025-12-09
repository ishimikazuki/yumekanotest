# 技術仕様書: ステート駆動型・オブザーバー協調チャットボットシステム

## 1. プロジェクト概要
本ドキュメントは、LLMを用いた対話システムにおいて、単一のプロンプトでは実現困難な「長期的記憶」「感情の揺らぎ」「シナリオ進行」を実装するためのオーケストレーションシステムの設計仕様である。

### アーキテクチャコンセプト
- **Observer-Actor Model:** 「状況を監視・更新するAI (Observer)」と「演技・発話を行うAI (Actor)」の役割を完全に分離する。
- **Stateful Memory:** 会話ごとの状態（State）を外部データベースにJSON形式で永続化し、これをBotの「記憶」および「脳」として扱う。

---

## 2. データベース設計 (Memory & State Schema)

Botの記憶と人格状態を保持するデータ構造。
このJSONオブジェクトが、会話のたびにObserverによって更新され、Actorによって参照される。

### 2.1 User State Object (メインメモリ)
`user_states` テーブル/コレクションに格納されるデータ構造。

```json
{
  "user_id": "U123456",
  "updated_at": "2025-12-05T12:00:00Z",
  
  // 【Module A: バイオリズム (不合理な人間性の再現)】
  // 会話の内容や乱数によって変動し、Botの口調や態度に影響を与える。
  "biometrics": {
    "mood": 5,          // 機嫌 (-10:激怒, 0:普通, 10:上機嫌)
    "energy": 80,       // 活力 (0:疲労困憊/睡眠, 100:元気)
    "affection": 45,    // 好感度 (0:他人, 100:最愛)
    "trust": 20         // 信頼度 (0:警戒, 100:秘密共有/シナリオ進行キー)
  },

  // 【Module B: シナリオステート (ゲーム進行管理)】
  // 物語の現在地を記録する。
  "scenario": {
    "current_phase": "phase_1_daily_life",  // 現在の章 ID
    "current_scene": "scene_living_room",   // 現在の場面 ID
    "turn_count_in_scene": 3,               // 場面内での経過ターン数
    "flags": {                              // イベントフラグ
      "has_met_before": true,
      "knows_secret_A": false,
      "trigger_event_confession": false
    }
  },

  // 【Module C: 長期記憶 (Fact Store)】
  // ユーザーに関する確定事項のリスト。
  "long_term_memories": [
    "ユーザーは東京在住",
    "辛い食べ物が苦手",
    "来週の日曜日にデートの約束をした"
  ]
}
```

### 2.2 Chat History (短期記憶)
`chat_logs` として直近N件（例：10件）のやり取りを保持。

```json
[
  {"role": "user", "content": "おはよう。眠そうだね。"},
  {"role": "assistant", "content": "ん...まだ眠いよ...。"}
]
```

---

## 3. エージェント機能要件

### 3.1 Observer Bot (The Logic Engine)
ユーザー入力と現在のStateを受け取り、**Stateの更新のみ**を行うエージェント。発話は行わない。

* **入力:** * ユーザーメッセージ
  * 現在の `User State Object`
* **処理ロジック:**
  1. **意図解析:** ユーザーの発言内容（好意的/攻撃的/質問 etc）を分析。
  2. **パラメータ計算:** ルールに基づき `mood`, `affection` を増減させる。
  3. **イベント判定:** `trust` が閾値を超えた、または特定のワードが出た場合、`scenario.flags` を更新する。
  4. **ファクト抽出:** 新しい個人情報があれば `long_term_memories` に追加する。
* **出力:** * 更新された `User State Object`
  * (任意) `instruction_override`: Main Botへの強制演技指導（例:「話題を逸らせ」）。

### 3.2 Main Bot / Actor (The Persona Engine)
更新されたStateを受け取り、**キャラクターになりきった発話のみ**を行うエージェント。

* **入力:** * ユーザーメッセージ
  * 会話履歴 (`Chat History`)
  * **更新後の** `User State Object`
  * `instruction_override` (存在する場合)
* **システムプロンプト構成:**
  * **前提:** あなたは {Character Name} です。
  * **状態:** 現在の機嫌は {mood}、活力は {energy} です。(数値に応じた演技指針を挿入)
  * **文脈:** 現在のシーンは {current_scene} です。
  * **記憶:** ユーザーについては {long_term_memories} を知っています。
  * **命令:** 以上の状態を踏まえ、自然な返答を生成してください。
* **出力:** * ユーザーへの返信テキスト

---

## 4. オーケストレーションフロー (実装ロジック)

以下はPythonによる疑似コードである。このロジックをバックエンド(FastAPI/Flask)またはn8nワークフローとして実装する。

```python
def process_chat_turn(user_id, user_message):
    
    # 1. Load State (記憶のロード)
    # DBから最新のステートとログを取得
    current_state = db.fetch_state(user_id)
    history = db.fetch_history(user_id)

    # 2. Observe Process (思考と更新)
    # Observer Botを呼び出し、新しいステートを計算させる
    # ※ここではテキスト生成ではなく、JSON生成(Function Calling/Structured Output)を使用
    observation_result = llm_observer.run(
        input_text=user_message,
        current_state=current_state
    )
    
    new_state = observation_result['updated_state']
    override_instr = observation_result.get('instruction_override')

    # 3. Save State (記憶の定着)
    # 更新された状態を即座にDBへコミット
    db.update_state(user_id, new_state)

    # 4. Act Process (発話生成)
    # 更新されたばかりの状態(new_state)を使って演技させる
    bot_response = llm_actor.run(
        input_text=user_message,
        history=history,
        state=new_state,  # <--- 重要: ここで最新の機嫌やシナリオが反映される
        instruction=override_instr
    )

    # 5. Log & Return
    db.save_log(user_id, user_message, bot_response)
    return bot_response
```

---

## 5. 推奨技術スタック
* **Orchestrator:** Python (FastAPI) または n8n / Dify
* **LLM:**
  * Observer: `gpt-4o-mini` (JSON出力が得意で高速・安価)
  * Actor: `grok-4-fast` (自然な日本語と演技力が高い)
* **Database:** 
* Google Sheets (プロトタイプ用 / 視認性が高い)
  * Supabase (本番用 / JSONデータの扱いに長ける)