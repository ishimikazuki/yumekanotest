"""Observer: ユーザーメッセージからステートを更新するロジック。

LLM が利用可能なら JSON 生成で更新し、未設定ならルールベースで動作する。
発話分類も行い、カテゴリに応じた処理を実行する。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional, Dict, Any

from .models import EmotionState, ObservationResult, UserState, UtteranceClassification, utc_now
from .llm_client import llm_client
from .settings import settings
from .prompt_loader import load_prompt
from .agent_logger import agent_logger
from .utterance_classifier import utterance_classifier, MultiClassificationResult

# シナリオデータのロード
SCENARIO_PATH = Path(__file__).resolve().parent / "data" / "idol_story.json"
SCENARIO_DATA = {}
if SCENARIO_PATH.exists():
    SCENARIO_DATA = json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))

DEFAULT_OBSERVER_SYSTEM_PROMPT = (
    "あなたはObserver役です。ユーザー発話と現在の状態を見て、感情パラメータ(PAD)とシナリオ進行を管理してください。\n"
    "出力は JSON のみ。\n"
    "emotion: pleasure, arousal, dominance (-10.0 to 10.0)\n"
    "scenario: variables (arbitrary key-values)\n"
    "instruction_override: Actorへの演技指導"
)

# 簡易ルールベース用キーワード
POSITIVE = ["好き", "楽しい", "嬉しい", "最高", "応援", "可愛い", "かわいい"]
NEGATIVE = ["嫌い", "つまらない", "最低", "うざい", "帰る"]
ACTIVE = ["行こう", "やる", "走る", "ダンス", "歌", "!"]

def _check_scenario_trigger(state: UserState, user_message: str = "", history: List[dict] = None) -> tuple[bool, Optional[str]]:
    """
    シナリオ遷移条件をチェックし、満たせば進行させる。

    Returns:
        tuple[bool, Optional[str]]: (遷移したか, Actorへの提案指示)
    """
    current_phase_id = state.scenario.current_phase
    phases = SCENARIO_DATA.get("phases", {})
    if current_phase_id not in phases:
        return (False, None)

    phase_def = phases[current_phase_id]
    next_phase_id = phase_def.get("next_phase")
    condition_expr = phase_def.get("trigger_condition")
    proposal_text = phase_def.get("proposal_text", "")  # 提案テキスト

    if not next_phase_id or not condition_expr:
        return (False, None)

    # ユーザーの同意をチェック（awaiting_consent中の場合）
    consent_for_next_phase = state.scenario.variables.get("consent_for_next_phase", False)

    if state.scenario.variables.get("awaiting_consent", False) and user_message:
        # 直前のアシスタント発話を取得（提案コンテキスト）
        proposal_context = None
        if history:
            for msg in reversed(history):
                if msg.get("role") == "assistant":
                    proposal_context = msg.get("content", "")
                    break

        # LLMで同意判定
        consent, confidence, reasoning = utterance_classifier.check_consent(
            utterance=user_message,
            proposal_context=proposal_context
        )
        print(f"[Observer] 同意判定: consent={consent}, confidence={confidence:.2f}, reason={reasoning}")

        if consent and confidence >= 0.6:
            state.scenario.variables["consent_for_next_phase"] = True
            consent_for_next_phase = True
        else:
            # 拒否された場合はawaiting_consentをリセット（再提案可能に）
            state.scenario.variables["awaiting_consent"] = False

    # 評価用コンテキスト作成
    context = {
        "turn_count_in_phase": state.scenario.turn_count_in_phase,
        "turn_count_in_scene": state.scenario.turn_count_in_phase,  # Alias
        "pleasure": state.emotion.pleasure,
        "arousal": state.emotion.arousal,
        "dominance": state.emotion.dominance,
        "variables": state.scenario.variables,
        "consent_for_next_phase": consent_for_next_phase,
    }

    # context変数を展開してeval (安全な簡易式のみ想定)
    try:
        if eval(condition_expr, {"__builtins__": None}, context):
            # 遷移実行
            state.scenario.current_phase = next_phase_id
            state.scenario.turn_count_in_phase = 0

            # 同意フラグをリセット
            state.scenario.variables["consent_for_next_phase"] = False
            state.scenario.variables["awaiting_consent"] = False

            # 新フェーズの初期シーンへ
            new_phase_def = phases.get(next_phase_id, {})
            scenes = new_phase_def.get("scenes", {})
            if scenes:
                state.scenario.current_scene = next(iter(scenes))

            return (True, None)
    except Exception as e:
        print(f"Trigger check error: {e}")

    # 遷移しない場合、提案条件をチェック（ターン条件のみ満たしている場合）
    # consent_for_next_phaseを除いた条件を評価
    if not consent_for_next_phase and not state.scenario.variables.get("awaiting_consent", False):
        try:
            # consent_for_next_phaseをTrueにして他の条件を評価
            context_for_proposal = context.copy()
            context_for_proposal["consent_for_next_phase"] = True

            if eval(condition_expr, {"__builtins__": None}, context_for_proposal):
                # ターン条件等は満たしている → 提案を指示
                state.scenario.variables["awaiting_consent"] = True
                next_phase_def = phases.get(next_phase_id, {})
                proposal_instruction = proposal_text or f"次のフェーズ「{next_phase_def.get('description', next_phase_id)}」への移行を提案してください。"
                return (False, proposal_instruction)
        except Exception as e:
            print(f"Proposal check error: {e}")

    return (False, None)

def _apply_keywords(text: str, emo: EmotionState) -> None:
    lowered = text
    if any(k in lowered for k in POSITIVE):
        emo.pleasure += 1.0
        emo.arousal += 0.5
    if any(k in lowered for k in NEGATIVE):
        emo.pleasure -= 1.5
        emo.dominance -= 0.5
    if any(k in lowered for k in ACTIVE):
        emo.arousal += 1.0

def _convert_classification(cls_result: MultiClassificationResult) -> tuple:
    """分類結果をモデル形式に変換"""
    primary = UtteranceClassification(
        category=cls_result.primary.category.value,
        confidence=cls_result.primary.confidence,
        extracted_info=cls_result.primary.extracted_info,
        reasoning=cls_result.primary.reasoning
    )
    secondary = [
        UtteranceClassification(
            category=s.category.value,
            confidence=s.confidence,
            extracted_info=s.extracted_info,
            reasoning=s.reasoning
        )
        for s in cls_result.secondary
    ]
    return primary, secondary


def update_state(user_message: str, state: UserState, history: List[dict]) -> ObservationResult:
    """ステートを更新し、必要に応じて指示を返す。"""
    provider = settings.llm.observer_provider
    model = settings.llm.observer_model

    # ログ開始
    agent_logger.start_agent(
        agent_name="observer",
        input_data={"user_message": user_message, "state": state.to_dict()},
        model=model,
        provider=provider
    )

    # 発話分類を実行
    classification_result = None
    primary_cls = None
    secondary_cls = []
    try:
        classification_result = utterance_classifier.classify(
            utterance=user_message,
            context=history,
            use_llm=llm_client.has(provider)
        )
        primary_cls, secondary_cls = _convert_classification(classification_result)
        print(f"[Observer] 発話分類: {primary_cls.category} (confidence: {primary_cls.confidence:.2f})")
    except Exception as e:
        print(f"[Observer] 発話分類エラー: {e}")

    # Try LLM update if available
    result = None
    if llm_client.has(provider):
        try:
            result = _update_state_llm(user_message, state, history, provider, classification_result)
            agent_logger.end_agent(
                agent_name="observer",
                output_data={
                    "emotion": result.updated_state.emotion.to_dict() if result else None,
                    "instruction": result.instruction_override if result else None,
                    "classification": primary_cls.to_dict() if primary_cls else None
                },
                details={"source": "llm"}
            )
        except Exception as e:
            agent_logger.error_agent(agent_name="observer", error=e)
            print(f"Observer LLM Failed: {e}. Falling back to rules.")
            result = None
    else:
        print(f"Observer provider '{provider}' not available. Using rules.")

    if result is None:
        # Fallback: Rule-based update
        new_state = UserState.from_dict(state.to_dict())
        _apply_keywords(user_message, new_state.emotion)
        new_state.emotion.clamp()
        new_state.emotion.decay(0.1)
        new_state.scenario.turn_count_in_phase += 1
        new_state.updated_at = utc_now()
        result = ObservationResult(
            updated_state=new_state,
            classification=primary_cls,
            secondary_classifications=secondary_cls
        )
        agent_logger.end_agent(
            agent_name="observer",
            output_data={
                "emotion": new_state.emotion.to_dict(),
                "classification": primary_cls.to_dict() if primary_cls else None
            },
            details={"source": "rules_fallback"}
        )
    else:
        # LLM結果に分類を追加
        result.classification = primary_cls
        result.secondary_classifications = secondary_cls

    # シナリオ遷移チェック (LLM更新後に判定)
    triggered, proposal_instruction = _check_scenario_trigger(
        result.updated_state,
        user_message=user_message,
        history=history
    )
    if triggered:
        # 遷移直後の指示でActorに知らせる
        result.instruction_override = (result.instruction_override or "") + " [SYSTEM: PHASE CHANGED]"
    elif proposal_instruction:
        # 提案指示をActorに渡す
        result.instruction_override = (result.instruction_override or "") + f" [SYSTEM: PROPOSE TRANSITION] {proposal_instruction}"

    return result


def _update_state_llm(
    user_message: str,
    state: UserState,
    history: List[dict],
    provider: str,
    classification: Optional[MultiClassificationResult] = None
) -> Optional[ObservationResult]:
    """OpenAI を用いた JSON 更新パス。"""
    system_prompt = load_prompt("observer_system", DEFAULT_OBSERVER_SYSTEM_PROMPT)
    
    # 現在のフェーズ情報を注入
    phase_id = state.scenario.current_phase
    phase_info = SCENARIO_DATA.get("phases", {}).get(phase_id, {})
    
    schema = {
        "type": "object",
        "properties": {
            "emotion": {
                "type": "object",
                "properties": {
                    "pleasure": {"type": "number"},
                    "arousal": {"type": "number"},
                    "dominance": {"type": "number"}
                },
                "required": ["pleasure", "arousal", "dominance"]
            },
            "scenario": {
                "type": "object",
                "properties": {
                    "variables": {"type": "object"}
                }
            },
            "instruction_override": {"type": ["string", "null"]}
        },
        "required": ["emotion", "scenario"]
    }
    
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"現在の状態: {state.to_dict()}\n"
                f"現在のフェーズ情報: {phase_info}\n"
                f"直近履歴: {history}\n"
                f"ユーザー発話: {user_message}"
            ),
        },
    ]
    data = llm_client.json_chat(
        model=settings.llm.observer_model,
        messages=messages,
        schema=schema,
        provider=provider,
        agent_type="observer",
    )

    new_state = UserState.from_dict(state.to_dict())
    
    # Emotion Update
    emo = data.get("emotion", {})
    new_state.emotion.pleasure = float(emo.get("pleasure", new_state.emotion.pleasure))
    new_state.emotion.arousal = float(emo.get("arousal", new_state.emotion.arousal))
    new_state.emotion.dominance = float(emo.get("dominance", new_state.emotion.dominance))
    new_state.emotion.clamp()
    
    # Scenario Vars Update
    scen = data.get("scenario", {})
    new_state.scenario.variables.update(scen.get("variables", {}))
    
    # 自然減衰 (Decay)
    new_state.emotion.decay(0.1) # 1回の会話で少し落ち着く
    
    # Turn Count
    new_state.scenario.turn_count_in_phase += 1
    new_state.updated_at = utc_now()
    
    override = data.get("instruction_override")
    return ObservationResult(updated_state=new_state, instruction_override=override)

