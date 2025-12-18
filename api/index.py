"""Vercel Python Function entrypoint - lightweight version."""

import os
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Observer-Actor Orchestration Bot", root_path="/api")

# プロンプトファイルの読み込み
def load_system_prompt() -> str:
    """actor_system.txtからシステムプロンプトを読み込む"""
    base_dir = Path(__file__).parent.parent
    prompt_path = base_dir / "orchestration" / "prompts" / "actor_system.txt"

    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")

    # フォールバック: 簡易プロンプト
    return "あなたはアイドルの「ゆめか」です。明るく元気な性格で、プロデューサーさんと話しています。"

SYSTEM_PROMPT = load_system_prompt()


class ChatRequest(BaseModel):
    user_id: str
    message: str


class DryRunRequest(BaseModel):
    enabled: bool


# ===== インメモリ状態管理 =====
_dry_run = False
_sessions: Dict[str, Dict[str, Any]] = {}  # user_id -> session data
_logs: List[Dict[str, Any]] = []  # Agent logs


def get_session(user_id: str) -> Dict[str, Any]:
    """ユーザーセッションを取得または作成"""
    if user_id not in _sessions:
        _sessions[user_id] = {
            "emotion": {"pleasure": 0.0, "arousal": 0.0, "dominance": 0.0},
            "history": [],
            "scenario": {"current_phase": "phase_first_encounter", "current_scene": "scene_station_front"}
        }
    return _sessions[user_id]


def add_log(agent_name: str, action: str, input_summary: str = "", output_summary: str = "", duration_ms: int = 0, error: str = ""):
    """ログを追加"""
    _logs.append({
        "timestamp": datetime.now().isoformat(),
        "agent_name": agent_name,
        "action": action,
        "input_summary": input_summary,
        "output_summary": output_summary,
        "duration_ms": duration_ms,
        "error": error
    })
    # 最大100件に制限
    if len(_logs) > 100:
        _logs.pop(0)


# ===== API エンドポイント =====

@app.get("/dryrun")
def get_dryrun_status():
    """DRY RUNモードの状態を取得"""
    return {"dry_run": _dry_run}


@app.post("/dryrun")
def set_dryrun(req: DryRunRequest):
    """DRY RUNモードを設定"""
    global _dry_run
    _dry_run = req.enabled
    add_log("system", "dryrun_toggle", output_summary=f"DRY RUN: {_dry_run}")
    return {"dry_run": _dry_run}


@app.post("/chat")
def chat(req: ChatRequest):
    """チャットエンドポイント（Vercel軽量版）"""
    start_time = time.time()
    session = get_session(req.user_id)

    # ユーザーメッセージを履歴に追加
    session["history"].append({"role": "user", "content": req.message})
    add_log("observer", "receive", input_summary=req.message[:100])

    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            add_log("actor", "error", error="OPENAI_API_KEY not set")
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")

        # DRY RUNモードの場合はAPIを呼ばない
        if _dry_run:
            reply = f"[DRY RUN] メッセージを受け取りました: {req.message[:50]}..."
            add_log("actor", "dry_run", output_summary=reply)
        else:
            # 会話履歴を含めてAPIを呼び出し
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            # 直近10件の履歴を含める
            for h in session["history"][-10:]:
                messages.append({"role": h["role"], "content": h["content"]})

            client = OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")

            actor_start = time.time()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            )
            actor_duration = int((time.time() - actor_start) * 1000)

            reply = response.choices[0].message.content
            add_log("actor", "generate", input_summary=req.message[:50], output_summary=reply[:100], duration_ms=actor_duration)

        # アシスタントの応答を履歴に追加
        session["history"].append({"role": "assistant", "content": reply})

        # 簡易的な感情分析（キーワードベース）
        emotion = session["emotion"]
        msg_lower = req.message.lower()
        if any(w in msg_lower for w in ["好き", "かわいい", "すごい", "嬉しい", "ありがとう"]):
            emotion["pleasure"] = min(10, emotion["pleasure"] + 1)
            emotion["arousal"] = min(10, emotion["arousal"] + 0.5)
        elif any(w in msg_lower for w in ["嫌い", "むかつく", "ダメ", "やめて"]):
            emotion["pleasure"] = max(-10, emotion["pleasure"] - 1)
            emotion["dominance"] = max(-10, emotion["dominance"] - 0.5)

        total_duration = int((time.time() - start_time) * 1000)
        add_log("orchestrator", "complete", output_summary=f"Total: {total_duration}ms", duration_ms=total_duration)

        return {
            "reply": reply,
            "state": {
                "emotion": emotion,
                "scenario": session["scenario"],
                "user_id": req.user_id
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        add_log("actor", "error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@app.post("/reset")
def reset(req: ChatRequest):
    """セッションリセット"""
    if req.user_id in _sessions:
        del _sessions[req.user_id]
    add_log("system", "reset", output_summary=f"Session reset for {req.user_id}")
    return {"status": "ok", "message": "Session reset complete."}


@app.get("/state/{user_id}")
def get_state(user_id: str):
    """状態取得"""
    session = get_session(user_id)
    return {
        "state": {
            "emotion": session["emotion"],
            "scenario": session["scenario"],
            "user_id": user_id
        },
        "history": session["history"]
    }


@app.get("/logs")
def get_logs(limit: int = 50):
    """ログ取得"""
    return {"logs": _logs[-limit:]}


@app.get("/logs/{agent_name}")
def get_agent_logs(agent_name: str, limit: int = 20):
    """エージェント別ログ取得"""
    filtered = [log for log in _logs if log["agent_name"] == agent_name]
    return {"logs": filtered[-limit:]}


@app.delete("/logs")
def clear_logs():
    """ログクリア"""
    global _logs
    _logs = []
    return {"status": "ok", "message": "Logs cleared"}
