"""CLI と（依存があれば）FastAPI エンドポイントを提供するエントリ。"""
from __future__ import annotations

import argparse
import sys
from typing import Optional
from pathlib import Path

from orchestration import ensure_storage_ready, process_chat_turn

# FastAPI は任意依存。未インストールなら app=None とする。
try:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except Exception:  # ImportError 以外も安全側で握り潰す
    FastAPI = None  # type: ignore
    BaseModel = object  # type: ignore

app: Optional["FastAPI"] = None


if FastAPI:

    class ChatRequest(BaseModel):
        user_id: str
        message: str

    app = FastAPI(title="Observer-Actor Orchestration Bot")
    app.mount("/static", StaticFiles(directory="ui"), name="static")

    @app.post("/chat")
    def chat(req: ChatRequest):
        try:
            result = process_chat_turn(req.user_id, req.message)
            state = result["state"].to_dict()
            return {"reply": result["reply"], "state": state}
        except Exception as e:
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"LLMエラー: {e}")

    @app.post("/reset")
    def reset(req: ChatRequest):
        from orchestration.orchestrator import reset_session
        try:
            reset_session(req.user_id)
            return {"status": "ok", "message": "Session reset complete."}
        except Exception as e:
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Reset Error: {e}")

    @app.get("/state/{user_id}")
    def get_state(user_id: str):
        from orchestration.storage import fetch_state, fetch_history

        state = fetch_state(user_id)
        history = fetch_history(user_id, limit=20)
        return {
            "state": state.to_dict() if state else None,
            "history": history,
        }

    @app.get("/", response_class=HTMLResponse)
    def ui_root():
        index_path = Path("ui/index.html")
        if index_path.exists():
            return index_path.read_text(encoding="utf-8")
        return "<h1>UIファイルが見つかりません</h1>"


def run_cli(user_id: str) -> None:
    ensure_storage_ready()
    print(f"ユーザーID: {user_id} で開始。終了するには 'exit' または Ctrl-D。")
    while True:
        try:
            user_msg = input("You> ").strip()
        except EOFError:
            print()
            break
        if user_msg.lower() in {"exit", "quit"}:
            break
        if not user_msg:
            continue
        try:
            result = process_chat_turn(user_id, user_msg)
            print("Bot>", result["reply"])
        except Exception as e:
            print(f"Error: {e}")
            print("エラーが発生しました。もう一度試すか、ログを確認してください。")
    print("会話を終了しました。")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Observer-Actor Chatbot Prototype")
    parser.add_argument("--user", default="demo", help="ユーザーID (既定: demo)")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="FastAPI サーバーを起動 (fastapi/uvicorn が必要)",
    )
    args = parser.parse_args(argv)

    if args.serve:
        if not app:
            print("FastAPI/uvicorn が見つかりません。`pip install fastapi uvicorn` を実行してください。")
            sys.exit(1)
        try:
            import uvicorn
        except Exception:
            print("uvicorn が見つかりません。`pip install uvicorn` を実行してください。")
            sys.exit(1)
        ensure_storage_ready()
        uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=False)
    else:
        run_cli(args.user)


if __name__ == "__main__":
    main()
