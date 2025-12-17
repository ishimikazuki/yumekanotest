"""階層メモリシステム

推奨: HierarchicalMemory を使用してください。

- ShortTermMemory: 短期記憶（最大15ターン）
- MidTermMemoryManager: 中期記憶（要約）
- LongTermMemoryManager: 長期記憶（ベクトル検索可能）
- HierarchicalMemory: 統合マネージャー

.. deprecated::
    memory_system (ChromaDB) は非推奨です。HierarchicalMemory を使用してください。
"""
from .memory_manager import HierarchicalMemory, RetrievedMemory
from .short_term import ShortTermMemory
from .mid_term import MidTermMemoryManager
from .long_term import LongTermMemoryManager

# 後方互換性のため残す（非推奨）
# 使用時に DeprecationWarning が発生します
from .vector_store import memory_system

__all__ = [
    "HierarchicalMemory",
    "RetrievedMemory",
    "ShortTermMemory",
    "MidTermMemoryManager",
    "LongTermMemoryManager",
    "memory_system",  # deprecated
]
