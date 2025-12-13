"""Supabaseクライアント"""
from __future__ import annotations

import os
from typing import Optional

try:
    from supabase import create_client, Client
except ImportError:
    create_client = None
    Client = None


class SupabaseClient:
    """Supabaseクライアントのシングルトン"""

    _instance: Optional["SupabaseClient"] = None
    _client: Optional[Client] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is not None:
            return

        if create_client is None:
            raise ImportError("supabase-py がインストールされていません。pip install supabase")

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_KEY")

        if not url or not key:
            raise ValueError("SUPABASE_URL と SUPABASE_ANON_KEY を .env に設定してください")

        self._client = create_client(url, key)

    @property
    def client(self) -> Client:
        if self._client is None:
            raise RuntimeError("Supabaseクライアントが初期化されていません")
        return self._client

    def table(self, name: str):
        """テーブルにアクセス"""
        return self.client.table(name)


# グローバルインスタンス
def get_supabase() -> SupabaseClient:
    return SupabaseClient()
