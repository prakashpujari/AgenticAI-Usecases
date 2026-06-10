"""Groq LLM client with model-chain fallback and graceful offline mode.

On any 429 / 503 / 529 (rate-limit / overloaded) or network error, the client
walks through the configured model chain and tries the next model.  Only after
every model in the chain is exhausted does it return the offline fallback JSON
— the pipeline never raises to the caller.

Default chain (overridable via env vars):
  1. llama-3.3-70b-versatile          (GROQ_MODEL)
  2. llama-3.1-8b-instant
  3. meta-llama/llama-4-scout-17b-16e-instruct
  4. moonshotai/kimi-k2-instruct       (GROQ_FALLBACK_MODELS)
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
# HTTP status codes that mean "this model is temporarily unavailable — try the next one"
_FALLTHROUGH_STATUSES = {429, 503, 529}


class GroqClient:
    """Calls the Groq API via httpx.  Falls through the model chain on transient errors."""

    def __init__(self) -> None:
        settings = get_settings()
        self.temperature = settings.groq_temperature
        self.max_tokens = settings.groq_max_tokens
        self.timeout = settings.groq_timeout_seconds

        _key = settings.groq_api_key
        _key_valid = bool(_key and not _key.startswith("your-"))
        if _key_valid:
            self._api_key: str | None = _key
        else:
            self._api_key = None
            logger.warning("Groq API key missing — running in offline fallback mode")

        # Build the ordered model chain: primary first, then unique fallbacks.
        primary = settings.groq_model
        fallbacks = [
            m.strip()
            for m in settings.groq_fallback_models.split(",")
            if m.strip()
        ]
        seen: set[str] = {primary}
        chain: list[str] = [primary]
        for m in fallbacks:
            if m not in seen:
                seen.add(m)
                chain.append(m)
        self._model_chain: list[str] = chain
        logger.info("Groq model chain: %s", " → ".join(chain))

    @property
    def is_live(self) -> bool:
        return self._api_key is not None

    # ── internal ───────────────────────────────────────────────────────────

    def _call(self, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        """Try each model in the chain in turn.  Never raises — returns offline JSON on total failure."""
        if not self.is_live:
            return self._offline_fallback(messages, json_mode=json_mode)

        last_err: Exception | None = None
        for model in self._model_chain:
            try:
                result = self._call_model(model, messages, json_mode=json_mode)
                if model != self._model_chain[0]:
                    logger.info("Used fallback model: %s", model)
                return result
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in _FALLTHROUGH_STATUSES:
                    logger.warning(
                        "Model %s returned %s — trying next model in chain", model, status
                    )
                    last_err = exc
                    continue
                # 400/404/401 etc. are not retryable — surface them immediately.
                if status == 401:
                    logger.error("Groq auth error — disabling live mode")
                    self._api_key = None
                    return self._offline_fallback(messages, json_mode=json_mode)
                raise
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                logger.warning(
                    "Model %s network error (%s) — trying next model in chain",
                    model, type(exc).__name__,
                )
                last_err = exc
                continue

        logger.error("All models in chain exhausted. Last error: %s", last_err)
        return self._offline_fallback(messages, json_mode=json_mode)

    def _call_model(self, model: str, messages: list[dict[str, str]], json_mode: bool = False) -> str:
        payload: dict[str, Any] = {
            "model": model,
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

        if response.status_code in _FALLTHROUGH_STATUSES:
            raise httpx.HTTPStatusError(
                f"model {model} unavailable ({response.status_code})",
                request=response.request,
                response=response,
            )

        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"] or ""

    # ── public API ─────────────────────────────────────────────────────────

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            return self._call(messages, json_mode=False)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Groq completion failed; using offline fallback. err=%s", exc)
            return self._offline_fallback(messages, json_mode=False)

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": system_prompt + "\n\nRespond with ONLY valid JSON."},
            {"role": "user", "content": user_prompt},
        ]
        raw = ""
        try:
            raw = self._call(messages, json_mode=True)
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Groq returned non-JSON content; attempting salvage")
            return self._salvage_json(raw)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Groq JSON completion failed; using offline fallback. err=%s", exc)
            return json.loads(self._offline_fallback(messages, json_mode=True))

    # ── helpers ────────────────────────────────────────────────────────────

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
                    "summary": "Offline mode — all Groq models unreachable. Returning deterministic placeholder.",
                    "score": 90,
                    "findings": [],
                    "echo": last_user[:200],
                }
            )
        return "Offline mode — all Groq models unreachable. Returning deterministic placeholder analysis."
