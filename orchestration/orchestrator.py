"""オーケストレーションの中核処理。"""
from __future__ import annotations

import os
from typing import Dict

from .actor import generate_reply
from .models import UserState
from .observer import update_state as observe
from .storage import fetch_state, init_db, update_state
from .memory.memory_manager import HierarchicalMemory

# ChromaDBはVercel環境では使用しない
IS_VERCEL = os.getenv("VERCEL") == "1"
vector_store = None
if not IS_VERCEL:
    try:
        from .memory import vector_store
    except Exception:
        pass

# 環境変数でLangGraphを有効化（デフォルトはfalse）
USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "false").lower() == "true"


def ensure_storage_ready() -> None:
    """DB 初期化を一度だけ実行。"""
    init_db()


def process_chat_turn(user_id: str, user_message: str) -> Dict:
    """
    チャットの1ターンを処理する。

    USE_LANGGRAPH=true の場合はLangGraphベースの処理を使用。
    それ以外は従来のCritic-Actorループを使用。
    """
    # LangGraph版を使う場合
    if USE_LANGGRAPH:
        return _process_chat_turn_langgraph(user_id, user_message)

    # 従来版
    return _process_chat_turn_legacy(user_id, user_message)


def _process_chat_turn_langgraph(user_id: str, user_message: str) -> Dict:
    """LangGraphベースの処理"""
    from .graph.dialogue_graph import run_dialogue_graph
    return run_dialogue_graph(user_id, user_message)


# ユーザーごとのメモリインスタンスを保持
_memory_instances: Dict[str, HierarchicalMemory] = {}


def get_memory(user_id: str) -> HierarchicalMemory:
    """ユーザーのメモリインスタンスを取得（なければ作成）"""
    if user_id not in _memory_instances:
        _memory_instances[user_id] = HierarchicalMemory(user_id)
    return _memory_instances[user_id]


def _process_chat_turn_legacy(user_id: str, user_message: str) -> Dict:
    """従来のCritic-Actorループベースの処理"""
    ensure_storage_ready()

    state = fetch_state(user_id)
    if state is None:
        state = UserState.new(user_id)

    # 階層メモリから会話履歴を取得
    memory = get_memory(user_id)
    history = memory.get_context()

    # ベクトル記憶にも入力を保存（モックしやすい副作用）
    if vector_store and hasattr(vector_store, 'memory_system') and vector_store.memory_system:
        vector_store.memory_system.save_memory(user_id, user_message, role="user", phase="interaction")

    # 1. Observer: ステート更新 (感情, シナリオ変遷)
    observation = observe(user_message, state, history)
    new_state = observation.updated_state
    update_state(user_id, new_state)

    # 2. Memory Retrieve: 過去の関連記憶を取得（長期記憶からベクトル検索）
    retrieved_memories = memory.retrieve(user_message, n_results=3)
    memory_texts = [m.content for m in retrieved_memories]

    # 中期・長期記憶からの要約コンテキストも追加
    summary_context = memory.get_summary_context()
    if summary_context:
        memory_texts.insert(0, summary_context)

    # 3. Actor & Critic Loop: 発話生成と自己批判
    from .critic import check_reply

    max_retries = 2
    current_instruction = observation.instruction_override
    final_reply = ""

    for attempt in range(max_retries + 1):
        # Actor: 発話生成
        reply = generate_reply(
            user_message=user_message,
            history=history,
            state=new_state,
            relevant_memories=memory_texts,
            instruction_override=current_instruction,
        )

        # Critic: 審査
        is_ok, feedback = check_reply(user_message, reply)

        if is_ok:
            final_reply = reply
            break
        else:
            print(f"[Critic NG] Attempt {attempt+1}: {feedback}")
            if current_instruction:
                current_instruction += f"\n[修正指示] {feedback}"
            else:
                current_instruction = f"[修正指示] {feedback}"

            if attempt == max_retries:
                print("[Critic] Max retries reached. Using last reply.")
                final_reply = reply

    # 4. 短期記憶にメッセージを追加（15ターンで中期→長期に昇格）
    memory.add_message("user", user_message)
    result = memory.add_message("assistant", final_reply)

    if result.get("promoted"):
        print(f"[Memory] 中期記憶に昇格: {result.get('summary', '')[:50]}...")

    # ベクトル記憶にアシスタント返答も保存
    if vector_store and hasattr(vector_store, 'memory_system') and vector_store.memory_system:
        vector_store.memory_system.save_memory(user_id, final_reply, role="assistant", phase="interaction")

    return {"reply": final_reply, "state": new_state}


def reset_session(user_id: str) -> None:
    """ユーザーの全データをリセットする。"""
    from .storage import reset_user

    # 階層メモリをクリア
    memory = get_memory(user_id)
    memory.clear_all()

    # メモリインスタンスを削除
    if user_id in _memory_instances:
        del _memory_instances[user_id]

    # DB（状態）をリセット
    reset_user(user_id)
