"""Value-chain decomposition (agentic, §6.4).

Decomposes a confirmed theme into ordered beneficiary nodes:
  direct → first_order → second_order → proxy

Both US and India tickers where applicable.
Gated: only runs when a model provider is configured.
"""
from __future__ import annotations

import logging

from backend import config
from backend.db import store
from backend.engine.model_provider import get_provider

log = logging.getLogger(__name__)

_TOOL_NAME = "submit_value_chain"
_TOOL_DESCRIPTION = "Submit the value-chain decomposition for an investment theme"
_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "node_role": {
                        "type": "string",
                        "enum": ["direct", "first_order", "second_order", "proxy"],
                    },
                    "company_name": {"type": "string"},
                    "ticker": {
                        "type": "string",
                        "description": "Stock ticker; empty string if private",
                    },
                    "exchange": {
                        "type": "string",
                        "enum": ["NYSE", "NASDAQ", "NSE", "BSE", "OTC", ""],
                    },
                    "linkage_tightness": {
                        "type": "string",
                        "enum": ["tight", "moderate", "loose"],
                    },
                    "justification": {
                        "type": "string",
                        "description": "1-sentence plain English explanation of why this company benefits",
                    },
                    "epistemic_tag": {
                        "type": "string",
                        "enum": ["V", "E", "I"],
                    },
                },
                "required": [
                    "node_role", "company_name", "ticker", "exchange",
                    "linkage_tightness", "justification", "epistemic_tag",
                ],
            },
        },
    },
    "required": ["nodes"],
}

_SYSTEM = (
    "You are an expert investment analyst mapping the beneficiaries of an emerging investment theme. "
    "Focus on the underlying ECONOMIC PRIMITIVE — who actually captures value when this theme plays out. "
    "Surface second-order plays a human scanning headlines would miss. "
    "Include both US-listed and India-listed (NSE/BSE) companies where applicable. "
    "Be honest about linkage tightness — only mark 'tight' when revenue is directly tied to this theme."
)


def _build_prompt(theme_name: str, primitive: str, thesis: str) -> str:
    return (
        f"Theme: {theme_name}\n"
        f"Economic primitive: {primitive}\n"
        f"What's happening now: {thesis}\n\n"
        f"Map the full value chain of beneficiaries. Rules:\n"
        f"- 'direct': companies at the exact center (2–3 max)\n"
        f"- 'first_order': companies making critical components/inputs for direct plays (3–5)\n"
        f"- 'second_order': less obvious suppliers, equipment makers, specialty inputs (3–5)\n"
        f"- 'proxy': indirect, speculative, or thematic connections — clearly labeled (2–3)\n"
        f"- Include India-listed beneficiaries where the economic primitive has Indian exposure\n"
        f"- Linkage 'tight' = revenue directly tied to this theme\n"
        f"- Linkage 'moderate' = meaningful but not primary revenue driver\n"
        f"- Linkage 'loose' = thematic, speculative connection"
    )


def run_value_chain(theme_id: str) -> list[dict] | None:
    """Run LLM value-chain decomposition. Returns list of node dicts or None."""
    provider = get_provider(config.VALUE_CHAIN_MODEL)
    if not provider:
        log.debug("value_chain skipped — no model provider configured")
        return None

    theme = store.get_theme(theme_id)
    if not theme:
        return None

    analysis = store.get_theme_analysis(theme_id)
    thesis = analysis["one_line_thesis"] if analysis else ""
    if not thesis:
        log.debug("value_chain skipped — no synthesis yet for %s", theme_id)
        return None

    result = provider.structured_completion(
        system=_SYSTEM,
        user=_build_prompt(theme["name"], theme.get("primitive", ""), thesis),
        tool_name=_TOOL_NAME,
        tool_description=_TOOL_DESCRIPTION,
        tool_schema=_TOOL_SCHEMA,
        max_tokens=2048,
    )
    if not result:
        return None

    nodes = [
        {
            "theme_id": theme_id,
            "node_role": n.get("node_role", "proxy"),
            "ticker": n.get("ticker", ""),
            "exchange": n.get("exchange", ""),
            "company_name": n.get("company_name", ""),
            "linkage_tightness": n.get("linkage_tightness", "loose"),
            "justification": n.get("justification", ""),
            "liquidity_flag": "ok",
            "epistemic_tag": n.get("epistemic_tag", "I"),
        }
        for n in result.get("nodes", [])
    ]
    store.replace_value_chain(theme_id, nodes)
    log.info("value_chain stored: %d nodes for %s", len(nodes), theme_id)
    return nodes
