"""Vercel Python Function entrypoint - Full orchestration version."""

import os
import sys
from pathlib import Path

# orchestrationモジュールのパスを追加
api_dir = Path(__file__).parent
project_root = api_dir.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# Vercel環境フラグ
IS_VERCEL = os.getenv("VERCEL") == "1"

app = FastAPI(title="Observer-Actor Orchestration Bot", root_path="/api")


class ChatRequest(BaseModel):
    user_id: str
    message: str


class DryRunRequest(BaseModel):
    enabled: bool


# ===== エンドポイント =====

@app.get("/dryrun")
def get_dryrun_status():
    """DRY RUNモードの状態を取得"""
    try:
        from orchestration.settings import settings
        return {"dry_run": settings.dry_run}
    except Exception as e:
        return {"dry_run": False, "error": str(e)}


@app.post("/dryrun")
def set_dryrun(req: DryRunRequest):
    """DRY RUNモードを設定"""
    try:
        from orchestration.settings import settings, enable_dry_run, disable_dry_run
        if req.enabled:
            enable_dry_run()
        else:
            disable_dry_run()
        return {"dry_run": settings.dry_run}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat")
def chat(req: ChatRequest):
    """チャットエンドポイント（完全版）"""
    try:
        from orchestration import process_chat_turn, ensure_storage_ready

        # ストレージ初期化（初回のみ実行される）
        ensure_storage_ready()

        # チャット処理
        result = process_chat_turn(req.user_id, req.message)

        # 状態をdict化
        state = result["state"]
        if hasattr(state, "to_dict"):
            state = state.to_dict()

        return {"reply": result["reply"], "state": state}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {e}")


@app.post("/reset")
def reset(req: ChatRequest):
    """セッションリセット"""
    try:
        from orchestration.orchestrator import reset_session
        reset_session(req.user_id)
        return {"status": "ok", "message": "Session reset complete."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reset Error: {e}")


@app.get("/state/{user_id}")
def get_state(user_id: str):
    """状態取得"""
    try:
        from orchestration.storage import fetch_state
        from orchestration.orchestrator import get_memory

        state = fetch_state(user_id)

        # Supabaseから履歴を取得（HierarchicalMemoryを使用）
        memory = get_memory(user_id)
        history = memory.get_context(limit=20)

        return {
            "state": state.to_dict() if state else None,
            "history": history,
        }
    except Exception as e:
        # エラー時はデフォルト値を返す
        return {
            "state": {
                "emotion": {"pleasure": 0.0, "arousal": 0.0, "dominance": 0.0},
                "user_id": user_id
            },
            "history": [],
            "error": str(e)
        }


@app.get("/logs")
def get_logs(limit: int = 50):
    """エージェントログを取得"""
    try:
        from orchestration.agent_logger import agent_logger
        return {"logs": agent_logger.get_recent_logs(limit)}
    except Exception as e:
        return {"logs": [], "error": str(e)}


@app.get("/logs/{agent_name}")
def get_agent_logs(agent_name: str, limit: int = 20):
    """特定エージェントのログを取得"""
    try:
        from orchestration.agent_logger import agent_logger
        return {"logs": agent_logger.get_logs_by_agent(agent_name, limit)}
    except Exception as e:
        return {"logs": [], "error": str(e)}


@app.delete("/logs")
def clear_logs():
    """ログをクリア"""
    try:
        from orchestration.agent_logger import agent_logger
        agent_logger.clear_logs()
        return {"status": "ok", "message": "Logs cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
