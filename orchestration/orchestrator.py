"""オーケストレーションの中核処理。"""
from __future__ import annotations

from typing import Dict

from .actor import generate_reply
from .models import UserState
from .observer import update_state as observe
from .storage import append_log, fetch_history, fetch_state, init_db, update_state
from .memory import memory_system


def ensure_storage_ready() -> None:
    """DB 初期化を一度だけ実行。"""
    init_db()


def process_chat_turn(user_id: str, user_message: str) -> Dict:
    ensure_storage_ready()

    state = fetch_state(user_id)
    if state is None:
        state = UserState.new(user_id)

    history = fetch_history(user_id)
    
    # 1. Observer: ステート更新 (感情, シナリオ変遷)
    observation = observe(user_message, state, history)
    new_state = observation.updated_state
    update_state(user_id, new_state)

    # 2. Memory Retrieve: 過去の関連記憶を取得
    # 直近の会話や今のフェーズに関連するものを探す
    memories = memory_system.retrieve_memory(user_id, user_message, n_results=3)
    memory_texts = [m.text for m in memories]

    # 3. Actor & Critic Loop: 発話生成と自己批判
    # CriticがNGを出した場合、フィードバックを与えて再生成する（最大2回）
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
            # 成功したらループを抜ける
            break
        else:
            print(f"[Critic NG] Attempt {attempt+1}: {feedback}")
            # フィードバックを次回の指示に追加
            # 元の指示があれば改行して追記
            if current_instruction:
                current_instruction += f"\n[修正指示] {feedback}"
            else:
                current_instruction = f"[修正指示] {feedback}"
            
            # 最後の試行だった場合、NGでもその回答を使う（無限ループ防止）
            if attempt == max_retries:
                print("[Critic] Max retries reached. Using last reply.")
                final_reply = reply

    # ログ保存 (短期記憶)
    append_log(user_id, "user", user_message)
    append_log(user_id, "assistant", final_reply)

    # 4. Memory Save: 長期記憶へ保存
    memory_system.save_memory(
        user_id, 
        f"User: {user_message}", 
        role="user", 
        phase=new_state.scenario.current_phase
    )
    memory_system.save_memory(
        user_id, 
        f"Me(Seira): {final_reply}", 
        role="assistant", 
        phase=new_state.scenario.current_phase
    )

    return {"reply": final_reply, "state": new_state}


def reset_session(user_id: str) -> None:
    """ユーザーの全データをリセットする。"""
    from .storage import reset_user
    from .memory import memory_system
    
    reset_user(user_id)
    memory_system.clear_memory(user_id)
