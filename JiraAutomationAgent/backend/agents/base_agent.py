"""
Base agent: async LLM caller with Redis prompt caching.
All specialised agents inherit from this class.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Optional

from openai import AsyncOpenAI

from ..config import settings
from ..services.redis_service import redis_service
from ..observability.tracer import log_cache_event, log_layer, log_layer_warn

# Wrap the OpenAI client with LangSmith instrumentation so every chat-
# completion call appears as a child "llm" span in LangSmith, properly
# nested under the parent @trace_agent span of whichever agent invokes it.
try:
    from langsmith.wrappers import wrap_openai as _ls_wrap_openai
    _LANGSMITH_WRAP_AVAILABLE = True
except ImportError:
    _LANGSMITH_WRAP_AVAILABLE = False

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Wraps an OpenAI chat call with:
      - A fixed system prompt (enforcing role separation)
      - Redis prompt caching (key: prompt:{sha256[:32]})
      - JSON-mode response format
    """

    def __init__(self, name: str, system_prompt: str) -> None:
        self.name = name
        self.system_prompt = system_prompt
        raw_client = AsyncOpenAI(api_key=settings.openai_api_key)
        # Wrap with LangSmith so all completions appear as child spans.
        # Falls back to the unwrapped client when langsmith is not installed.
        self._client = _ls_wrap_openai(raw_client) if _LANGSMITH_WRAP_AVAILABLE else raw_client

    # ------------------------------------------------------------------

    def _cache_key(self, messages: list) -> str:
        # Deterministic key: sort_keys ensures dict ordering doesn't affect the hash.
        # Truncated to 32 hex chars (128 bits) — sufficient collision resistance
        # for a prompt cache where a miss is merely a slow path, not a failure.
        content = json.dumps(messages, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    # ------------------------------------------------------------------

    async def call(
        self,
        user_message: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        use_cache: bool = True,
    ) -> str:
        """
        Send *user_message* to the LLM (with this agent's system prompt).
        Checks Redis cache first; stores the response on a cache miss.
        Always requests JSON-mode output.
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message},
        ]
        cache_key = self._cache_key(messages)

        prompt_chars = sum(len(m["content"]) for m in messages)

        # ── Cache lookup ──────────────────────────────────────────────
        if use_cache:
            cached = await redis_service.get_prompt_cache(cache_key)
            if cached:
                log_cache_event("prompt", cache_key, hit=True)
                log_layer("LLM", self.name,
                          cache="HIT",
                          model=settings.openai_model,
                          prompt_chars=prompt_chars)
                return cached
        log_cache_event("prompt", cache_key, hit=False)

        # ── LLM call ──────────────────────────────────────────────────
        log_layer("LLM", self.name,
                  direction="→",
                  model=settings.openai_model,
                  temp=temperature,
                  max_tokens=max_tokens,
                  prompt_chars=prompt_chars,
                  cache="MISS")

        t0 = time.monotonic()
        response = await self._client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        latency = time.monotonic() - t0
        content: str = response.choices[0].message.content or "{}"

        usage = response.usage
        finish = response.choices[0].finish_reason

        log_layer("LLM", self.name,
                  direction="←",
                  model=settings.openai_model,
                  tokens=f"{usage.total_tokens}({usage.prompt_tokens}p+{usage.completion_tokens}c)",
                  latency_s=f"{latency:.2f}",
                  finish=finish)

        if finish == "length":
            log_layer_warn("LLM", self.name,
                           warning="finish_reason=length — response may be truncated",
                           max_tokens=max_tokens)

        # ── Store in cache ────────────────────────────────────────────
        if use_cache:
            await redis_service.set_prompt_cache(cache_key, content)

        # Keep legacy log line so existing parsers that grep for it continue to work
        logger.info("[%s] LLM call completed (tokens: %s)", self.name, usage.total_tokens)
        return content
