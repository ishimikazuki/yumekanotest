"""LLM クライアントラッパー。

- OpenAI: 通常の API
- xAI (Grok): OpenAI 互換エンドポイントを base_url で指定
- DRY_RUN=true: APIを呼ばずにテストデータを返す
"""
from __future__ import annotations

import json
import random
from typing import Any, Dict, List, Optional

from .settings import settings

try:
    from openai import OpenAI
except Exception:  # ImportError 他
    OpenAI = None  # type: ignore


# DRY RUN用のテストレスポンス
DRY_RUN_RESPONSES = {
    "observer": {
        "emotion": {"pleasure": 2.0, "arousal": 1.5, "dominance": 0.5},
        "scenario": {"variables": {}},
        "instruction_override": None
    },
    "actor": [
        "あっ、こんにちはですっ！今日はどうしたんですか？",
        "えへへ、嬉しいですっ！わたしに会いに来てくれたんですね！",
        "ふふっ、そうなんですか？もっと教えてくださいっ！",
        "わたし、蒼井セイラって言います。よろしくお願いしますっ！",
    ],
    "critic": {
        "is_ok": True,
        "feedback": ""
    }
}


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
        agent_type: Optional[str] = None,  # "observer", "actor", "critic" for dry run
    ) -> str:
        # DRY RUNモードの場合はテストデータを返す
        if settings.dry_run:
            return self._dry_run_response(agent_type or "actor")

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

    def json_chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        provider: str,
        agent_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """JSON schema を指定した structured 出力。"""
        # DRY RUNモードの場合はテストデータを返す
        if settings.dry_run:
            return self._dry_run_json_response(agent_type or "observer")

        content = self.chat(
            model=model,
            messages=messages,
            provider=provider,
            response_format={"type": "json_object", "schema": schema},
        )
        return json.loads(content)

    def _dry_run_response(self, agent_type: str) -> str:
        """DRY RUN用のテキストレスポンスを返す"""
        if agent_type == "actor":
            return random.choice(DRY_RUN_RESPONSES["actor"])
        elif agent_type == "critic":
            return json.dumps(DRY_RUN_RESPONSES["critic"])
        else:
            return json.dumps(DRY_RUN_RESPONSES.get(agent_type, {"message": "dry run"}))

    def _dry_run_json_response(self, agent_type: str) -> Dict[str, Any]:
        """DRY RUN用のJSONレスポンスを返す"""
        return DRY_RUN_RESPONSES.get(agent_type, {"status": "dry_run"})


    def embed(self, text: str, model: str = "text-embedding-3-small") -> List[float]:
        """テキストをベクトル化する（OpenAI Embedding API）"""
        if settings.dry_run:
            # DRY RUNモードでは1536次元のダミーベクトルを返す
            import hashlib
            # テキストのハッシュを使って一貫したダミーベクトルを生成
            hash_val = int(hashlib.md5(text.encode()).hexdigest(), 16)
            random.seed(hash_val)
            return [random.uniform(-1, 1) for _ in range(1536)]

        # OpenAIクライアントを使用（embeddingはOpenAI APIのみ）
        client = self.clients.get("openai")
        if not client:
            raise RuntimeError("OpenAI client is required for embeddings")

        resp = client.embeddings.create(
            model=model,
            input=text
        )
        return resp.data[0].embedding


llm_client = LLMClient()
