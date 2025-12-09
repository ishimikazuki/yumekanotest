"""Observer: ユーザーメッセージからステートを更新するロジック。

LLM が利用可能なら JSON 生成で更新し、未設定ならルールベースで動作する。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional, Dict, Any

from .models import EmotionState, ObservationResult, UserState, utc_now
from .llm_client import llm_client
from .settings import settings
from .prompt_loader import load_prompt

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

def _check_scenario_trigger(state: UserState) -> bool:
    """シナリオ遷移条件をチェックし、満たせば進行させる。"""
    current_phase_id = state.scenario.current_phase
    phases = SCENARIO_DATA.get("phases", {})
    if current_phase_id not in phases:
        return False
    
    phase_def = phases[current_phase_id]
    next_phase_id = phase_def.get("next_phase")
    condition_expr = phase_def.get("trigger_condition")
    
    if not next_phase_id or not condition_expr:
        return False

    # 評価用コンテキスト作成
    context = {
        "turn_count_in_phase": state.scenario.turn_count_in_phase,
        "turn_count_in_scene": state.scenario.turn_count_in_phase,  # Alias
        "pleasure": state.emotion.pleasure,
        "arousal": state.emotion.arousal,
        "dominance": state.emotion.dominance,
        "variables": state.scenario.variables
    }
    
    # context変数を展開してeval (安全な簡易式のみ想定)
    # 例: "pleasure >= 5.0" -> 5.0 >= 5.0 -> True
    try:
        # 安全性のための最低限のサンドボックス（完全ではないが）
        allowed_names = context.keys()
        if eval(condition_expr, {"__builtins__": None}, context):
            # 遷移実行
            state.scenario.current_phase = next_phase_id
            state.scenario.turn_count_in_phase = 0
            
            # 新フェーズの初期シーンへ
            new_phase_def = phases.get(next_phase_id, {})
            scenes = new_phase_def.get("scenes", {})
            if scenes:
                state.scenario.current_scene = next(iter(scenes)) # 最初のシーン
                
            return True
    except Exception as e:
        print(f"Trigger check error: {e}")
        
    return False

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

def update_state(user_message: str, state: UserState, history: List[dict]) -> ObservationResult:
    """ステートを更新し、必要に応じて指示を返す。"""
    provider = settings.llm.observer_provider
    if not llm_client.has(provider):
         raise RuntimeError(f"Observer LLM provider '{provider}' not available")

    result = None
    try:
        result = _update_state_llm(user_message, state, history, provider)
    except Exception as e:
        raise RuntimeError(f"Observer LLM Failed: {e}")

    if result is None:
        raise RuntimeError("Observer LLM returned no data")
    
    # シナリオ遷移チェック (LLM更新後に判定)
    triggered = _check_scenario_trigger(result.updated_state)
    if triggered:
        # 遷移直後の指示でActorに知らせる
        result.instruction_override = (result.instruction_override or "") + " [SYSTEM: PHASE CHANGED]"

    return result


def _update_state_llm(user_message: str, state: UserState, history: List[dict], provider: str) -> Optional[ObservationResult]:
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

