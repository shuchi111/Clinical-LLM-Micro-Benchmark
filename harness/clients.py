"""LLM provider clients. One job: system+user -> Completion."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol

from harness.config import require_env
from harness.io_util import curl_json


@dataclass
class Completion:
    text: str
    model_name: str
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def usage(self) -> Any:
        return self.raw.get("usage") or self.raw.get("usageMetadata")

    @property
    def response_id(self) -> Any:
        return self.raw.get("id")


class LLMClient(Protocol):
    provider: str
    model: str
    endpoint: str

    def complete(self, system: str, user: str) -> Completion: ...


class ZAIClient:
    """Z.AI Anthropic-compatible /v1/messages."""

    provider = "zai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        url: str | None = None,
    ):
        self.api_key = api_key or require_env("ZAI_API_KEY")
        self.model = model or os.getenv("ZAI_MODEL", "glm-5.1")
        self.endpoint = url or os.getenv(
            "ZAI_URL", "https://api.z.ai/api/anthropic/v1/messages"
        )

    def complete(self, system: str, user: str) -> Completion:
        body = {
            "model": self.model,
            "max_tokens": 1024,
            "temperature": 0,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        code, data = curl_json(
            self.endpoint,
            {"x-api-key": self.api_key},
            body,
        )
        if code != 200:
            raise RuntimeError(f"Z.AI HTTP {code}: {data}")
        parts = data.get("content") or []
        text = "".join(
            p.get("text", "")
            for p in parts
            if isinstance(p, dict) and p.get("type") == "text"
        )
        if not text and isinstance(data.get("content"), str):
            text = data["content"]
        if not text:
            raise RuntimeError(f"Empty Z.AI content: {list(data.keys())}")
        return Completion(text=text, model_name=data.get("model") or self.model, raw=data)


class GroqClient:
    """Groq OpenAI-compatible chat completions."""

    provider = "groq"
    endpoint = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or require_env("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def complete(self, system: str, user: str) -> Completion:
        body = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        code, data = curl_json(
            self.endpoint,
            {"Authorization": f"Bearer {self.api_key}"},
            body,
        )
        if code != 200:
            raise RuntimeError(f"Groq HTTP {code}: {data}")
        if "error" in data:
            raise RuntimeError(f"Groq error: {data['error']}")
        text = data["choices"][0]["message"]["content"]
        return Completion(text=text, model_name=data.get("model") or self.model, raw=data)


class GeminiClient:
    """Google Generative Language generateContent."""

    provider = "google"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = (
            api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or require_env("GEMINI_API_KEY")
        )
        self.model = (
            model
            or os.getenv("GOOGLE_MODEL")
            or os.getenv("GEMINI_MODEL")
            or "gemini-2.5-flash"
        )

    @property
    def endpoint(self) -> str:
        return (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )

    def complete(self, system: str, user: str) -> Completion:
        url = f"{self.endpoint}?key={self.api_key}"
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0},
        }
        code, data = curl_json(url, {}, body)
        if code != 200:
            raise RuntimeError(f"Gemini HTTP {code}: {data}")
        if "error" in data:
            raise RuntimeError(f"Gemini error: {data['error']}")
        cands = data.get("candidates") or []
        if not cands:
            raise RuntimeError(f"No Gemini candidates: {data}")
        parts = (((cands[0] or {}).get("content") or {}).get("parts")) or []
        text = "".join(p.get("text", "") for p in parts)
        if not text:
            raise RuntimeError(f"Empty Gemini text: {data}")
        return Completion(
            text=text,
            model_name=data.get("modelVersion") or self.model,
            raw=data,
        )


PROVIDERS = {
    "zai": ZAIClient,
    "groq": GroqClient,
    "gemini": GeminiClient,
    "google": GeminiClient,
}


def make_client(name: str) -> LLMClient:
    key = name.lower().strip()
    if key not in PROVIDERS:
        raise SystemExit(f"Unknown provider {name!r}. Choose: {', '.join(PROVIDERS)}")
    return PROVIDERS[key]()
