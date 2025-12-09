"""LLM クライアントラッパー。

- OpenAI: 通常の API
- xAI (Grok): OpenAI 互換エンドポイントを base_url で指定
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .settings import settings

try:
    from openai import OpenAI
except Exception:  # ImportError 他
    OpenAI = None  # type: ignore


class LLMClient:
    def __init__(self):
        self.clients: Dict[str, Optional[Any]] = {"openai": None, "xai": None}
        if OpenAI:
            if settings.llm.api_key:
                # base_url が None の場合は引数に渡さない (OpenAIデフォルトを使う)
                kwargs = {"api_key": settings.llm.api_key}
                if settings.llm.openai_base_url:
                    kwargs["base_url"] = settings.llm.openai_base_url
                self.clients["openai"] = OpenAI(**kwargs)

            if settings.llm.xai_api_key:
                self.clients["xai"] = OpenAI(
                    api_key=settings.llm.xai_api_key,
                    base_url=settings.llm.xai_base_url,
                )

    @property
    def available(self) -> bool:
        return any(self.clients.values())

    def has(self, provider: str) -> bool:
        return provider in self.clients and self.clients[provider] is not None

    def _pick(self, provider: str):
        client = self.clients.get(provider)
        if client:
            return client
        raise RuntimeError(f"LLM provider '{provider}' is not available")

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        provider: str,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        client = self._pick(provider)
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format=response_format,
        )
        content = resp.choices[0].message.content
        if not content:
            raise RuntimeError("LLM returned empty content")
        return content

    def json_chat(self, model: str, messages: List[Dict[str, str]], schema: Dict[str, Any], provider: str) -> Dict[str, Any]:
        """JSON schema を指定した structured 出力。"""
        content = self.chat(
            model=model,
            messages=messages,
            provider=provider,
            response_format={"type": "json_object", "schema": schema},
        )
        return json.loads(content)


llm_client = LLMClient()
