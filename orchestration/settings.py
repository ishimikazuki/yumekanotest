"""環境変数と設定値のローダー。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # 依存未インストールでも動作するようにする
    pass


@dataclass
class LLMSettings:
    api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    observer_model: str = os.getenv("OBSERVER_MODEL", "gpt-4o-mini")
    actor_model: str = os.getenv("ACTOR_MODEL", "grok-4-fast")
    observer_provider: str = os.getenv("OBSERVER_PROVIDER", "openai")  # openai | xai
    actor_provider: str = os.getenv("ACTOR_PROVIDER", "xai")  # openai | xai
    xai_api_key: Optional[str] = os.getenv("XAI_API_KEY")
    xai_base_url: str = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
    openai_base_url: Optional[str] = os.getenv("OPENAI_BASE_URL")


@dataclass
class AppSettings:
    llm: LLMSettings = field(default_factory=LLMSettings)
    db_path: Path = Path("data/bot.db")
    chroma_db_path: Path = Path("data/chroma_db")
    rules_path: Path = Path("data/rules/behavior_rules.json")
    use_langgraph: bool = os.getenv("USE_LANGGRAPH", "false").lower() == "true"
    dry_run: bool = os.getenv("DRY_RUN", "false").lower() == "true"


settings = AppSettings()


def enable_dry_run():
    """DRY RUNモードを有効化（テスト用）"""
    settings.dry_run = True


def disable_dry_run():
    """DRY RUNモードを無効化"""
    settings.dry_run = False
