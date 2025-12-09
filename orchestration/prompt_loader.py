from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


@lru_cache(maxsize=None)
def load_prompt(name: str, default: str) -> str:
    """指定名のプロンプトを読み込む。欠損時は default を返す。

    手書きで編集しやすいテキストファイルを優先し、空ファイルや例外時も安全にフォールバックする。
    """
    path = PROMPT_DIR / f"{name}.txt"
    try:
        text = path.read_text(encoding="utf-8")
        if text.strip():
            return text
    except FileNotFoundError:
        pass
    except Exception:
        return default
    return default
