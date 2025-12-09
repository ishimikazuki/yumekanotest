"""Actor: ステートに応じた演技的レスポンスを生成する。

LLM が利用可能なら生成系を使用し、未設定ならテンプレートで返す。
"""
from __future__ import annotations

import random
from typing import List, Optional

from .models import UserState
from .llm_client import llm_client
from .settings import settings
from .prompt_loader import load_prompt

DEFAULT_ACTOR_SYSTEM_PROMPT = (
    "あなたはActor役のキャラクターです。以下の現在状態に沿って日本語で自然に返答してください。\n"
    "必須条件:\n"
    "- 感情(PAD)とシナリオ(Phase/Scene)に合わせて演技すること\n"
    "- 注入された「長期記憶」をヒントに、過去の文脈を踏まえた発言をすること\n"
    "- instruction_override があれば優先\n"
)


def _tone_from_emotion(emo: EmotionState) -> str:
    # PADモデルに基づく演技指針の生成
    tone = []
    if emo.pleasure >= 5.0:
        tone.append("明るく楽しげに")
    elif emo.pleasure <= -5.0:
        tone.append("不機嫌に、冷たく")
    
    if emo.arousal >= 5.0:
        tone.append("テンション高く")
    elif emo.arousal <= -5.0:
        tone.append("落ち着いて、あるいは眠げに")
        
    if emo.dominance >= 5.0:
        tone.append("自信満々に")
    elif emo.dominance <= -5.0:
        tone.append("控えめに、おどおどと")
        
    return "、".join(tone) if tone else "自然体で"


def generate_reply(
    user_message: str,
    history: List[dict],
    state: UserState,
    relevant_memories: List[str],  # 検索された長期記憶
    instruction_override: Optional[str] = None,
) -> str:
    provider = settings.llm.actor_provider
    if not llm_client.has(provider):
        raise RuntimeError(f"Actor LLM provider '{provider}' not available")
    
    try:
        reply = _generate_reply_llm(user_message, history, state, relevant_memories, instruction_override, provider)
    except Exception as e:
        raise RuntimeError(f"Actor LLM Failed: {e}")

    if not reply:
        raise RuntimeError("Actor LLM returned empty content")
        
    return reply.strip()


def _generate_reply_llm(
    user_message: str,
    history: List[dict],
    state: UserState,
    memories: List[str],
    instruction_override: Optional[str],
    provider: str,
) -> Optional[str]:
    system_prompt = load_prompt("actor_system", DEFAULT_ACTOR_SYSTEM_PROMPT)
    
    # メモリをテキスト化
    memory_text = "\n".join([f"- {m}" for m in memories]) if memories else "特になし"
    tone_instruction = _tone_from_emotion(state.emotion)
    
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"現在の状態: {state.to_dict()}\n"
                f"演技指針(PAD由来): {tone_instruction}\n"
                f"関連する長期記憶: \n{memory_text}\n"
                f"instruction_override: {instruction_override}\n"
                f"直近会話履歴: {history[-3:]}\n"
                f"ユーザー発話: {user_message}"
            ),
        },
    ]
    try:
        return llm_client.chat(
            model=settings.llm.actor_model,
            messages=messages,
            provider=provider,
        )
    except Exception:
        return None


def _reflect(message: str, mood: int) -> str:
    """シンプルな言い換えで相手の発話に寄り添う。"""
    if "?" in message or "？" in message:
        return "気になることがあるんだね。一緒に考えるよ。"
    if mood <= -4:
        return "正直少しイライラしてるけど、聞いてる。"
    if "ごめん" in message or "すまん" in message:
        return "謝らなくて大丈夫、気持ちは伝わったよ。"
    return "なるほど、そう感じたんだね。"
