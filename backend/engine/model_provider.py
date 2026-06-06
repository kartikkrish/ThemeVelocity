"""Provider abstraction for structured LLM completions.

Supported providers:
  anthropic  — Anthropic Claude via native SDK (default)
  gemini     — Google Gemini via OpenAI-compatible endpoint
  ollama     — Any Ollama model via local OpenAI-compatible endpoint

Configuration via env vars:
  TV_MODEL_PROVIDER   anthropic | gemini | ollama   (default: anthropic)
  MODEL_API_KEY       API key for anthropic or gemini
                      Falls back to ANTHROPIC_API_KEY for backward compatibility.
  TV_MODEL_BASE_URL   Base URL for ollama (default: http://localhost:11434/v1)
                      Can also point any other OpenAI-compatible endpoint.

Example overrides:
  # Use Gemini Flash for synthesis, Gemini Pro for value chain
  TV_MODEL_PROVIDER=gemini
  MODEL_API_KEY=<google_ai_studio_key>
  TV_SYNTHESIS_MODEL=gemini-1.5-flash
  TV_VALUE_CHAIN_MODEL=gemini-1.5-pro

  # Use a local Ollama model
  TV_MODEL_PROVIDER=ollama
  TV_MODEL_BASE_URL=http://localhost:11434/v1
  TV_SYNTHESIS_MODEL=llama3.1
  TV_VALUE_CHAIN_MODEL=llama3.1:70b
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class IModelProvider(ABC):
    """
    Minimal interface: system prompt + user prompt + tool definition → structured dict.

    Callers never construct providers directly — use get_provider().
    """

    @abstractmethod
    def structured_completion(
        self,
        *,
        system: str,
        user: str,
        tool_name: str,
        tool_description: str,
        tool_schema: dict,
        max_tokens: int = 1024,
    ) -> dict | None:
        """
        Force the model to call *tool_name* and return its input dict.
        Returns None on failure or if the provider is not available.
        """


class AnthropicProvider(IModelProvider):
    """Uses the native Anthropic SDK — best tool-use reliability for Claude models."""

    def __init__(self, api_key: str, model: str) -> None:
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def structured_completion(
        self, *, system, user, tool_name, tool_description, tool_schema, max_tokens=1024
    ) -> dict | None:
        tool = {
            "name": tool_name,
            "description": tool_description,
            "input_schema": tool_schema,
        }
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": user}],
            )
            for block in resp.content:
                if block.type == "tool_use" and block.name == tool_name:
                    return block.input
        except Exception as exc:
            log.warning("[anthropic/%s] structured_completion failed: %s", self._model, exc)
        return None


class OpenAICompatProvider(IModelProvider):
    """
    Handles any OpenAI-compatible chat-completions endpoint:
      - Google Gemini  → https://generativelanguage.googleapis.com/v1beta/openai/
      - Ollama         → http://localhost:11434/v1
      - Any self-hosted vLLM / LM Studio / etc.
    """

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "The 'openai' package is required for Gemini/Ollama providers. "
                "Install it with:  pip install openai"
            ) from exc
        self._client = OpenAI(base_url=base_url, api_key=api_key or "none")
        self._model = model

    def structured_completion(
        self, *, system, user, tool_name, tool_description, tool_schema, max_tokens=1024
    ) -> dict | None:
        tool = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_description,
                "parameters": tool_schema,
            },
        }
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                tools=[tool],
                tool_choice={"type": "function", "function": {"name": tool_name}},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            msg = resp.choices[0].message
            if msg.tool_calls:
                return json.loads(msg.tool_calls[0].function.arguments)
        except Exception as exc:
            log.warning("[openai-compat/%s] structured_completion failed: %s", self._model, exc)
        return None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def _effective_settings() -> dict:
    """
    Merge DB settings (higher priority) over env-var config (lower priority).
    Returns a flat dict with keys: provider, api_key, base_url,
    synthesis_model, value_chain_model.
    """
    from backend import config
    from backend.db import store

    db = store.get_model_settings()
    return {
        "provider":         db.get("provider")         or config.MODEL_PROVIDER,
        "api_key":          db.get("api_key")          or config.MODEL_API_KEY,
        "base_url":         db.get("base_url")         or config.MODEL_BASE_URL,
        "synthesis_model":  db.get("synthesis_model")  or config.SYNTHESIS_MODEL,
        "value_chain_model": db.get("value_chain_model") or config.VALUE_CHAIN_MODEL,
    }


# Small local models whose structured classification (e.g. catalyst_type) is unreliable.
# Their free-text (thesis) is usable, but enum classification should be flagged low-confidence.
_LOW_CONFIDENCE_MODEL_HINTS = ("qwen", "gemma", "llama", "mistral", "phi", "ollama")


def is_low_confidence_model(model: str | None) -> bool:
    """True if `model` is a small local model whose enum classifications shouldn't be trusted."""
    if not model:
        return False
    m = model.lower()
    return any(h in m for h in _LOW_CONFIDENCE_MODEL_HINTS)


def get_synthesis_model() -> str:
    return _effective_settings()["synthesis_model"]


def get_value_chain_model() -> str:
    return _effective_settings()["value_chain_model"]


def get_provider(model: str, *, _settings: dict | None = None) -> IModelProvider | None:
    """
    Return the configured provider for *model*, or None if not available.

    Reads live settings from DB (overrides env vars) so provider switches
    take effect immediately without restart.

    _settings: pre-fetched settings dict (used internally to avoid double DB read).
    """
    cfg = _settings or _effective_settings()
    ptype = cfg["provider"].lower()

    if ptype == "auto":
        m = model.lower()
        if "claude" in m:
            ptype = "anthropic"
        elif "gemini" in m:
            ptype = "gemini"
        else:
            ptype = "ollama"

    if ptype == "anthropic":
        if not cfg["api_key"]:
            log.debug("anthropic provider disabled — set MODEL_API_KEY or ANTHROPIC_API_KEY")
            return None
        return AnthropicProvider(api_key=cfg["api_key"], model=model)

    if ptype == "gemini":
        if not cfg["api_key"]:
            log.debug("gemini provider disabled — set MODEL_API_KEY")
            return None
        return OpenAICompatProvider(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=cfg["api_key"],
            model=model,
        )

    if ptype == "ollama":
        return OpenAICompatProvider(
            base_url=cfg["base_url"] or "http://localhost:11434/v1",
            api_key="ollama",
            model=model,
        )

    log.warning("Unknown provider=%r — model layer disabled", cfg["provider"])
    return None
