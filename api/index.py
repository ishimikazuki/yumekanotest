"""Vercel Python Function entrypoint.

FastAPI アプリを公開するだけで、uvicorn は不要です。
Rewrite で付与した `__path` クエリを使い、元のパスに戻してルーティングします。
"""

from fastapi import Request
from main import app  # FastAPI インスタンスをそのままエクスポート


@app.middleware("http")
async def restore_path_middleware(request: Request, call_next):
    """
    Vercel の rewrite で `/api/index.py?__path=/chat` のように流れてくるため、
    ルータが正しく動くよう scope.path を元パスに書き戻す。
    """
    original = request.query_params.get("__path")
    if original:
        # path と raw_path を書き換え
        request.scope["path"] = original
        request.scope["raw_path"] = original.encode("utf-8")
    response = await call_next(request)
    return response
