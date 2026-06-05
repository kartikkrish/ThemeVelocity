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

def get_provider(model: str) -> IModelProvider | None:
    """
    Return the configured provider for *model*, or None if not available.

    Provider selection order:
      1. TV_MODEL_PROVIDER env var
      2. Auto-detect from model name (claude→anthropic, gemini→gemini, else→ollama)
    """
    from backend import config

    ptype = config.MODEL_PROVIDER.lower()

    if ptype == "auto":
        m = model.lower()
        if "claude" in m:
            ptype = "anthropic"
        elif "gemini" in m:
            ptype = "gemini"
        else:
            ptype = "ollama"

    if ptype == "anthropic":
        if not config.MODEL_API_KEY:
            log.debug("anthropic provider disabled — set MODEL_API_KEY or ANTHROPIC_API_KEY")
            return None
        return AnthropicProvider(api_key=config.MODEL_API_KEY, model=model)

    if ptype == "gemini":
        if not config.MODEL_API_KEY:
            log.debug("gemini provider disabled — set MODEL_API_KEY")
            return None
        return OpenAICompatProvider(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=config.MODEL_API_KEY,
            model=model,
        )

    if ptype == "ollama":
        return OpenAICompatProvider(
            base_url=config.MODEL_BASE_URL or "http://localhost:11434/v1",
            api_key="ollama",
            model=model,
        )

    log.warning("Unknown TV_MODEL_PROVIDER=%r — model layer disabled", config.MODEL_PROVIDER)
    return None
