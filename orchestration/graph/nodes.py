"""LangGraphのノード関数定義"""
from typing import Dict, List, Any

from .state import GraphState
from ..models import UserState
from ..rules.rule_registry import RuleRegistry
from ..rules.rule_selector import RuleSelector
from ..validation.output_validator import OutputValidator
from ..validation.output_fixer import OutputFixer


# シングルトンインスタンス（遅延初期化）
_registry = None
_rule_selector = None
_validator = None
_fixer = None


def _get_registry() -> RuleRegistry:
    global _registry
    if _registry is None:
        _registry = RuleRegistry.get_instance()
    return _registry


def _get_rule_selector() -> RuleSelector:
    global _rule_selector
    if _rule_selector is None:
        _rule_selector = RuleSelector(_get_registry())
    return _rule_selector


def _get_validator() -> OutputValidator:
    global _validator
    if _validator is None:
        _validator = OutputValidator()
    return _validator


def _get_fixer() -> OutputFixer:
    global _fixer
    if _fixer is None:
        _fixer = OutputFixer()
    return _fixer


def node_load_state(state: GraphState) -> Dict[str, Any]:
    """初期状態のロード"""
    from ..storage import fetch_state, fetch_history, init_db

    init_db()

    user_state = fetch_state(state["user_id"])
    if user_state is None:
        user_state = UserState.new(state["user_id"])

    history = fetch_history(state["user_id"])

    return {
        "user_state": user_state,
        "history": history,
        "retry_count": 0,
        "max_retries": 2,
        "errors": [],
        "memories": [],
        "draft_reply": "",
        "final_reply": "",
        "validation_result": None,
        "instruction_override": None,
        "selected_rules": None,
    }


def node_observe(state: GraphState) -> Dict[str, Any]:
    """Observer: 状態更新"""
    from ..observer import update_state as observe
    from ..storage import update_state as save_state

    try:
        observation = observe(
            state["user_message"],
            state["user_state"],
            state["history"],
        )

        # 状態を保存
        save_state(state["user_id"], observation.updated_state)

        return {
            "user_state": observation.updated_state,
            "instruction_override": observation.instruction_override,
        }

    except Exception as e:
        print(f"[node_observe] Error: {e}")
        return {
            "errors": state.get("errors", []) + [f"Observer error: {e}"],
        }


def node_retrieve_memory(state: GraphState) -> Dict[str, Any]:
    """Memory: 関連記憶の取得"""
    from ..memory import memory_system

    try:
        memories = memory_system.retrieve_memory(
            state["user_id"],
            state["user_message"],
            n_results=3,
        )
        memory_texts = [m.text for m in memories]

        return {
            "memories": memory_texts,
        }

    except Exception as e:
        print(f"[node_retrieve_memory] Error: {e}")
        return {
            "memories": [],
            "errors": state.get("errors", []) + [f"Memory error: {e}"],
        }


def node_select_rules(state: GraphState) -> Dict[str, Any]:
    """RuleSelector: 適用ルールの選択"""
    try:
        selector = _get_rule_selector()
        selected = selector.select_rules(
            state=state["user_state"],
            user_message=state["user_message"],
            history=state["history"],
        )

        return {
            "selected_rules": selected,
        }

    except Exception as e:
        print(f"[node_select_rules] Error: {e}")
        return {
            "errors": state.get("errors", []) + [f"RuleSelector error: {e}"],
        }


def node_generate(state: GraphState) -> Dict[str, Any]:
    """Actor: 発話生成"""
    from ..actor import generate_reply

    try:
        # ルール要約を instruction に追加
        instruction = state.get("instruction_override") or ""
        if state.get("selected_rules"):
            # 要約は長すぎるので、重要な部分だけ
            rules = state["selected_rules"]
            if rules.state_dependent_rules:
                sdr_hints = [
                    r.prompt_hint or r.description
                    for r in rules.state_dependent_rules
                    if r.prompt_hint or r.description
                ]
                if sdr_hints:
                    instruction += "\n\n[状態依存ルール]\n" + "\n".join(f"- {h}" for h in sdr_hints[:3])

            if rules.allow_nsfw:
                instruction += "\n\n[NSFW許可: このフェーズでは性的な描写が許可されています]"

        draft = generate_reply(
            user_message=state["user_message"],
            history=state["history"],
            state=state["user_state"],
            relevant_memories=state.get("memories", []),
            instruction_override=instruction if instruction else None,
        )

        return {
            "draft_reply": draft,
        }

    except Exception as e:
        print(f"[node_generate] Error: {e}")
        return {
            "draft_reply": "",
            "errors": state.get("errors", []) + [f"Actor error: {e}"],
        }


def node_validate(state: GraphState) -> Dict[str, Any]:
    """Validator: 出力検証"""
    try:
        validator = _get_validator()

        if not state.get("selected_rules"):
            # ルールがなければスキップ
            return {
                "validation_result": None,
            }

        result = validator.validate(
            output_text=state["draft_reply"],
            user_message=state["user_message"],
            selected_rules=state["selected_rules"],
            history=state["history"],
        )

        return {
            "validation_result": result,
        }

    except Exception as e:
        print(f"[node_validate] Error: {e}")
        return {
            "validation_result": None,
            "errors": state.get("errors", []) + [f"Validator error: {e}"],
        }


def node_fix(state: GraphState) -> Dict[str, Any]:
    """Fixer: 出力修正"""
    try:
        fixer = _get_fixer()

        if not state.get("validation_result"):
            return {
                "retry_count": state.get("retry_count", 0) + 1,
            }

        fix_result = fixer.fix(
            original_text=state["draft_reply"],
            validation_result=state["validation_result"],
            user_message=state["user_message"],
        )

        if fix_result.success:
            return {
                "draft_reply": fix_result.fixed_text,
                "retry_count": state.get("retry_count", 0) + 1,
            }
        else:
            # 修正失敗（BLOCKなど）
            return {
                "retry_count": state.get("retry_count", 0) + 1,
                "errors": state.get("errors", []) + ["Fix failed: blocked content"],
            }

    except Exception as e:
        print(f"[node_fix] Error: {e}")
        return {
            "retry_count": state.get("retry_count", 0) + 1,
            "errors": state.get("errors", []) + [f"Fixer error: {e}"],
        }


def node_save(state: GraphState) -> Dict[str, Any]:
    """Save: ログ保存と応答確定"""
    from ..storage import append_log
    from ..memory import memory_system

    final_reply = state["draft_reply"]

    try:
        # ログ保存
        append_log(state["user_id"], "user", state["user_message"])
        append_log(state["user_id"], "assistant", final_reply)

        # 長期記憶保存
        current_phase = state["user_state"].scenario.current_phase if state.get("user_state") else "unknown"

        memory_system.save_memory(
            state["user_id"],
            f"User: {state['user_message']}",
            role="user",
            phase=current_phase,
        )
        memory_system.save_memory(
            state["user_id"],
            f"Me(Seira): {final_reply}",
            role="assistant",
            phase=current_phase,
        )

    except Exception as e:
        print(f"[node_save] Error: {e}")

    return {
        "final_reply": final_reply,
    }


def should_retry(state: GraphState) -> str:
    """リトライ判定の条件分岐"""
    validation_result = state.get("validation_result")

    # 検証結果がなければ保存へ
    if validation_result is None:
        return "save"

    # 検証OKなら保存へ
    if validation_result.is_valid:
        return "save"

    # リトライ上限に達したら保存へ（妥協）
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 2)
    if retry_count >= max_retries:
        print(f"[should_retry] Max retries ({max_retries}) reached. Using current reply.")
        return "save"

    # 違反があるので修正へ
    return "fix"
