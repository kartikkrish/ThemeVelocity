"""Theme Synthesis Engine (agentic, triggered on velocity breach).

FR-SYN-1: Produces one_line_thesis, catalyst_type, maturity_stage, key_entities
FR-SYN-2: Catalyst classification (earnings / product / regulatory / narrative / …)
FR-SYN-3: Noise/meme filter — LLM judges whether spike is tradable or manipulated
FR-SYN-4: V/E/I epistemic tags on all claims

Gated: only runs when a model provider is configured. Degrades gracefully without one.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from backend import config
from backend.db import store
from backend.engine.model_provider import get_provider, get_synthesis_model

log = logging.getLogger(__name__)

_TOOL_NAME = "submit_synthesis"
_TOOL_DESCRIPTION = "Submit structured theme synthesis result"
_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "one_line_thesis": {
            "type": "string",
            "description": (
                "Plain-English 1-sentence explanation of why this theme matters for investors "
                "RIGHT NOW — no jargon, accessible to a smart non-specialist."
            ),
        },
        "catalyst_type": {
            "type": "string",
            "enum": [
                "earnings_guidance", "product_launch", "regulatory_change",
                "order_flow", "tech_breakthrough", "macro_shift", "pure_narrative",
            ],
        },
        "catalyst_detail": {
            "type": "string",
            "description": "1-sentence plain English description of the specific catalyst driving current acceleration.",
        },
        "maturity_stage": {
            "type": "string",
            "enum": ["early_discovery", "building_momentum", "mainstream_known"],
        },
        "is_real_theme": {
            "type": "boolean",
            "description": "Is this a genuine business/investment theme vs noise or coordinated pump?",
        },
        "noise_reason": {
            "type": ["string", "null"],
            "description": "If is_real_theme=false, brief explanation. Else null.",
        },
        "key_entities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Up to 5 company/technology names most central to this theme.",
        },
        "epistemic_tag": {
            "type": "string",
            "enum": ["V", "E", "I"],
            "description": "V=verified by filings/announcements, E=analyst estimates, I=inferred from narrative.",
        },
    },
    "required": [
        "one_line_thesis", "catalyst_type", "catalyst_detail",
        "maturity_stage", "is_real_theme", "key_entities", "epistemic_tag",
    ],
}

_SYSTEM = (
    "You are a senior investment analyst synthesizing early-stage theme signals. "
    "Your output will be shown directly to investors — write in plain, accessible English. "
    "No jargon. No acronyms without explanation. Be honest about uncertainty."
)


def _build_prompt(theme_name: str, primitive: str, events: list[str]) -> str:
    sample = "\n".join(f"• {e}" for e in events[:25])
    return (
        f"Theme: {theme_name}\n"
        f"Underlying driver: {primitive}\n\n"
        f"Recent signals from specialist sources (last 48h):\n{sample}\n\n"
        f"Synthesize what is happening RIGHT NOW with this theme. "
        f"Focus on what's NEW or ACCELERATING — not background context."
    )


def run_synthesis(theme_id: str) -> dict | None:
    """Run LLM synthesis for a theme. Returns the result dict or None if unavailable."""
    provider = get_provider(get_synthesis_model())
    if not provider:
        log.debug("synthesis skipped — no model provider configured")
        return None

    theme = store.get_theme(theme_id)
    if not theme:
        return None

    since = datetime.now(timezone.utc) - timedelta(hours=48)
    events = [
        r["raw_text"]
        for r in store.get_recent_theme_events(theme_id, since, limit=25)
        if r.get("raw_text")
    ]
    if len(events) < 3:
        log.debug("synthesis skipped — too few events (%d) for %s", len(events), theme_id)
        return None

    return provider.structured_completion(
        system=_SYSTEM,
        user=_build_prompt(theme["name"], theme.get("primitive", ""), events),
        tool_name=_TOOL_NAME,
        tool_description=_TOOL_DESCRIPTION,
        tool_schema=_TOOL_SCHEMA,
        max_tokens=1024,
    )


def synthesize_and_store(theme_id: str, velocity_result) -> dict | None:
    """Run synthesis + confidence, persist to theme_analysis. Returns stored row or None."""
    result = run_synthesis(theme_id)
    if not result:
        return None

    from backend.engine.confidence import compute_confidence
    score = compute_confidence(velocity_result, result)

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "theme_id": theme_id,
        "analyzed_at": now,
        "one_line_thesis": result.get("one_line_thesis", ""),
        "is_real_theme": int(result.get("is_real_theme", True)),
        "catalyst_type": result.get("catalyst_type", ""),
        "catalyst_detail": result.get("catalyst_detail", ""),
        "maturity_stage": result.get("maturity_stage", ""),
        "earliness": velocity_result.earliness,
        "c_velocity": score.c_velocity,
        "c_source": score.c_source,
        "c_catalyst": score.c_catalyst,
        "c_earliness": score.c_earliness,
        "c_linkage": score.c_linkage,
        "c_liquidity": score.c_liquidity,
        "c_total": score.c_total,
        "dominant_tag": score.epistemic_tag,
    }
    store.upsert_theme_analysis(row)
    return row
