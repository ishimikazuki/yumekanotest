from __future__ import annotations

import chromadb
from chromadb.config import Settings
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

from .settings import settings

@dataclass
class MemoryItem:
    text: str
    metadata: dict
    distance: float = 0.0

class MemorySystem:
    def __init__(self):
        # ChromaDB Client の初期化
        # データは data/chroma に永続化
        self.client = chromadb.PersistentClient(path=str(settings.chroma_db_path))
        self.collection = self.client.get_or_create_collection(name="idol_memories")

    def save_memory(self, user_id: str, text: str, role: str, phase: str) -> None:
        """記憶を保存する。"""
        # IDはタイムスタンプ + ランダムなどで一意にする
        import uuid
        mem_id = str(uuid.uuid4())
        
        now_str = datetime.now().isoformat()
        
        self.collection.add(
            documents=[text],
            metadatas=[{
                "user_id": user_id,
                "role": role,
                "timestamp": now_str,
                "phase": phase
            }],
            ids=[mem_id]
        )

    def retrieve_memory(self, user_id: str, query_text: str, n_results: int = 3) -> List[MemoryItem]:
        """関連する記憶を検索する。"""
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where={"user_id": user_id}
        )
        
        memories = []
        if results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            dists = results["distances"][0] if results["distances"] else [0.0] * len(docs)
            
            for doc, meta, dist in zip(docs, metas, dists):
                memories.append(MemoryItem(text=doc, metadata=meta, distance=dist))
                
        return memories

    def clear_memory(self, user_id: str) -> None:
        """ 特定ユーザーの記憶を全削除する。"""
        # delete メソッドは where 句で指定した全ドキュメントを削除
        try:
             self.collection.delete(where={"user_id": user_id})
        except Exception:
            # 何もない場合などにエラーになる実装かどうか不明だが、念のため握りつぶすかログ出す
            pass

# Singleton instance
memory_system = MemorySystem()
