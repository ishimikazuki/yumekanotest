import json
from pathlib import Path
from typing import Tuple

from .llm_client import llm_client
from .settings import settings
from .prompt_loader import load_prompt

def check_reply(user_message: str, draft_reply: str) -> Tuple[bool, str]:
    """
    Critic AIを使って、生成された回答がキャラクター設定・ルールに合致しているか判定する。
    Return: (is_ok: bool, feedback: str)
    """
    # prompt_loaderを使って読み込む（引数はfilename_w/o_ext）
    system_prompt = load_prompt("critic_system", "You are a strict critic.")
    
    # Observer/Actorと同じProvider/Modelを使うか、設定で分けるかだが、
    # ここではObserver（論理エンジン）と同じものを使用する。
    provider = settings.llm.observer_provider
    model = settings.llm.observer_model
    
    user_content = f"### User Input\n{user_message}\n\n### Bot Draft Reply\n{draft_reply}"
    
    try:
        response_text = llm_client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            provider=provider,
            response_format={"type": "json_object"}
        ) or "{}"
        
        # JSONパース
        cleaned = response_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned)
        
        return data.get("is_ok", False), data.get("feedback", "")
        
    except Exception as e:
        print(f"[Critic Error] {e}")
        return True, ""
