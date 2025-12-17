"""ベクトル記憶ストア（ChromaDB）。

短期・中期メモリとは別に、ユーザー発話や応答をベクトル化して
検索できるようにするためのシンプルな永続ストア。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List

import chromadb
from chromadb.config import Settings

from ..settings import settings


@dataclass
class MemoryItem:
    text: str
    metadata: dict
    distance: float = 0.0


class MemorySystem:
    def __init__(self):
        # ChromaDB Client の初期化（データは data/chroma に永続化）
        self.client = chromadb.PersistentClient(path=str(settings.chroma_db_path))
        self.collection = self.client.get_or_create_collection(name="idol_memories")

    def save_memory(self, user_id: str, text: str, role: str, phase: str) -> None:
        """記憶を保存する。"""
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

        memories: List[MemoryItem] = []
        if results["documents"]:
            docs = results["documents"][0]
            metas = results["metadatas"][0]
            dists = results["distances"][0] if results["distances"] else [0.0] * len(docs)

            for doc, meta, dist in zip(docs, metas, dists):
                memories.append(MemoryItem(text=doc, metadata=meta, distance=dist))

        return memories

    def clear_memory(self, user_id: str) -> None:
        """特定ユーザーの記憶を全削除する。"""
        try:
            self.collection.delete(where={"user_id": user_id})
        except Exception:
            # 空削除などは握りつぶす
            pass


# Singleton instance
memory_system = MemorySystem()

