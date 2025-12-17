"""Vercel Python Function entrypoint - lightweight version."""

import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Observer-Actor Orchestration Bot", root_path="/api")


class ChatRequest(BaseModel):
    user_id: str
    message: str


class DryRunRequest(BaseModel):
    enabled: bool


# シンプルなインメモリ状態
_dry_run = False


@app.get("/dryrun")
def get_dryrun_status():
    """DRY RUNモードの状態を取得"""
    return {"dry_run": _dry_run}


@app.post("/dryrun")
def set_dryrun(req: DryRunRequest):
    """DRY RUNモードを設定"""
    global _dry_run
    _dry_run = req.enabled
    return {"dry_run": _dry_run}


@app.post("/chat")
def chat(req: ChatRequest):
    """チャットエンドポイント（Vercel軽量版）"""
    try:
        # 重い依存関係なしの簡易実装
        # 実際のorchestrationは重い依存関係が必要なため、
        # Vercelでは動作しません
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "あなたはアイドルの「ゆめか」です。明るく元気な性格で、プロデューサーさんと話しています。"},
                {"role": "user", "content": req.message}
            ]
        )

        reply = response.choices[0].message.content
        return {
            "reply": reply,
            "state": {
                "emotion": {"P": 0.5, "A": 0.5, "D": 0.5},
                "user_id": req.user_id
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@app.post("/reset")
def reset(req: ChatRequest):
    """セッションリセット"""
    return {"status": "ok", "message": "Session reset complete."}


@app.get("/state/{user_id}")
def get_state(user_id: str):
    """状態取得（簡易版）"""
    return {
        "state": {
            "emotion": {"P": 0.5, "A": 0.5, "D": 0.5},
            "user_id": user_id
        },
        "history": []
    }


@app.get("/logs")
def get_logs(limit: int = 50):
    """ログ取得（簡易版）"""
    return {"logs": []}


@app.get("/logs/{agent_name}")
def get_agent_logs(agent_name: str, limit: int = 20):
    """エージェントログ（簡易版）"""
    return {"logs": []}


@app.delete("/logs")
def clear_logs():
    """ログクリア"""
    return {"status": "ok", "message": "Logs cleared"}
