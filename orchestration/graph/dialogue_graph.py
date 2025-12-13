"""LangGraph対話グラフ定義"""
from typing import Dict, Any, Optional

from .state import GraphState
from .nodes import (
    node_load_state,
    node_observe,
    node_retrieve_memory,
    node_select_rules,
    node_generate,
    node_validate,
    node_fix,
    node_save,
    should_retry,
)

# LangGraphのインポート（利用可能な場合のみ）
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    print("[dialogue_graph] Warning: langgraph not installed. Using fallback.")


def create_dialogue_graph():
    """対話グラフを構築"""
    if not LANGGRAPH_AVAILABLE:
        return None

    graph = StateGraph(GraphState)

    # ノード追加
    graph.add_node("load_state", node_load_state)
    graph.add_node("observe", node_observe)
    graph.add_node("retrieve_memory", node_retrieve_memory)
    graph.add_node("select_rules", node_select_rules)
    graph.add_node("generate", node_generate)
    graph.add_node("validate", node_validate)
    graph.add_node("fix", node_fix)
    graph.add_node("save", node_save)

    # エントリーポイント
    graph.set_entry_point("load_state")

    # 順次エッジ
    graph.add_edge("load_state", "observe")
    graph.add_edge("observe", "retrieve_memory")
    graph.add_edge("retrieve_memory", "select_rules")
    graph.add_edge("select_rules", "generate")
    graph.add_edge("generate", "validate")

    # 条件分岐エッジ
    graph.add_conditional_edges(
        "validate",
        should_retry,
        {
            "save": "save",
            "fix": "fix",
        }
    )

    # 修正後は再生成へ
    graph.add_edge("fix", "generate")

    # 保存後は終了
    graph.add_edge("save", END)

    return graph.compile()


def run_dialogue_graph(user_id: str, user_message: str) -> Dict[str, Any]:
    """対話グラフを実行"""
    if not LANGGRAPH_AVAILABLE or dialogue_graph is None:
        # フォールバック: 既存のprocess_chat_turnを使用
        from ..orchestrator import process_chat_turn
        return process_chat_turn(user_id, user_message)

    # 初期状態
    initial_state: GraphState = {
        "user_id": user_id,
        "user_message": user_message,
        "user_state": None,
        "history": [],
        "memories": [],
        "selected_rules": None,
        "draft_reply": "",
        "final_reply": "",
        "validation_result": None,
        "retry_count": 0,
        "max_retries": 2,
        "instruction_override": None,
        "errors": [],
    }

    # グラフ実行
    final_state = dialogue_graph.invoke(initial_state)

    return {
        "reply": final_state.get("final_reply", ""),
        "state": final_state.get("user_state"),
    }


# グラフのシングルトンインスタンス
dialogue_graph = create_dialogue_graph() if LANGGRAPH_AVAILABLE else None
