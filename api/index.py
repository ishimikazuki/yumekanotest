"""Vercel Python Function entrypoint.

FastAPI アプリを公開するだけで、uvicorn は不要です。
"""

from main import app  # FastAPI インスタンスをそのままエクスポート

