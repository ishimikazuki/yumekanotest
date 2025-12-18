"""オーケストレーションBot パッケージ。"""

import os

from .orchestrator import process_chat_turn, ensure_storage_ready
from .utterance_classifier import (
    UtteranceClassifier,
    UtteranceCategory,
    utterance_classifier,
)
from .models import UtteranceClassification

# ChromaDBはVercel環境では使用しない（遅延インポート）
memory_system = None
MemoryItem = None

# Vercel以外の環境でのみChromaDBをインポート
if not os.getenv("VERCEL"):
    try:
        from .memory.vector_store import memory_system, MemoryItem
    except Exception:
        pass  # ChromaDBが使えない環境では無視

__all__ = [
    "process_chat_turn",
    "ensure_storage_ready",
    "UtteranceClassifier",
    "UtteranceCategory",
    "utterance_classifier",
    "UtteranceClassification",
    "memory_system",
    "MemoryItem",
]
