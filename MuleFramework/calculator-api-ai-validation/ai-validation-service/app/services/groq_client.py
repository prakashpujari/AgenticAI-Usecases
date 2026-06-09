"""Groq LLM client with structured JSON output, retries, and graceful fallback.

If the Groq SDK or API key is unavailable, completions return a deterministic
fallback string so the LangGraph pipeline can still complete end-to-end in
CI / offline mode.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = logging.getLogger(__name__)

_GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
_RETRYABLE = (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)


class GroqClient:
    """Calls the Groq API directly via httpx with explicit timeouts."""

    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.groq_model
        self.temperature = settings.groq_temperature
        self.max_tokens = settings.groq_max_tokens
        self.timeout = settings.groq_timeout_seconds

        _key = settings.groq_api_key
        _key_valid = bool(_key and not _key.startswith("your-"))
        if _key_valid:
            self._api_key: str | None = _key
            logger.info("Groq client initialized model=%s", self.model)
        else:
            self._api_key = None
            logger.warning("Groq API key missing — running in offline fallback mode")

    @property
    def is_live(self) -> bool:
        return self._api_key is not None

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(_RETRYABLE),
        reraise=True,
    )
    def _call(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        if not self.is_live:
            return self._offline_fallback(messages, json_mode=json_mode)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        timeout = httpx.Timeout(connect=5.0, read=self.timeout, write=10.0, pool=5.0)
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                _GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if response.status_code == 401:
            logger.error("Groq auth error — falling back to offline mode")
            self._api_key = None
            return self._offline_fallback(messages, json_mode=json_mode)

        if response.status_code == 429:
            raise httpx.HTTPStatusError("rate limited", request=response.request, response=response)

        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"] or ""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            return self._call(messages, json_mode=False)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Groq completion failed; using fallback. err=%s", exc)
            return self._offline_fallback(messages, json_mode=False)

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": system_prompt + "\n\nRespond with ONLY valid JSON."},
            {"role": "user", "content": user_prompt},
        ]
        try:
            raw = self._call(messages, json_mode=True)
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Groq returned non-JSON content; attempting salvage")
            return self._salvage_json(raw if isinstance(raw, str) else "")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Groq JSON completion failed; using fallback. err=%s", exc)
            return json.loads(self._offline_fallback(messages, json_mode=True))

    @staticmethod
    def _salvage_json(text: str) -> dict[str, Any]:
        try:
            start = text.find("{")
            end = text.rfind("}")
            if 0 <= start < end:
                return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
        return {"summary": text.strip() or "no content", "findings": []}

    @staticmethod
    def _offline_fallback(messages: list[dict[str, str]], json_mode: bool) -> str:
        last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
        if json_mode:
            return json.dumps(
                {
                    "summary": "Offline mode — Groq API not reachable. Deterministic analysis returned.",
                    "score": 90,
                    "findings": [],
                    "echo": last_user[:200],
                }
            )
        return "Offline mode — Groq API not reachable. Returning deterministic placeholder analysis."
