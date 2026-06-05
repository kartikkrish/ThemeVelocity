"""India cross-map (Phase 4 agentic stage).

Given a confirmed US theme + its economic primitive + existing value chain,
identifies Indian-listed companies (NSE/BSE/SME) exposed to the same primitive.

All outputs default to [I] epistemic tag unless a hard catalyst upgrades them.
Mandatory linkage-tightness and liquidity flags per FR-IN-4.
"""
from __future__ import annotations
import logging
from backend import config
from backend.db import store
from backend.engine.model_provider import get_provider, get_value_chain_model

log = logging.getLogger(__name__)

_TOOL_NAME = "submit_india_crossmap"
_TOOL_DESCRIPTION = "Submit India cross-map beneficiaries for a US investment theme"
_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "india_nodes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "ticker": {"type": "string", "description": "NSE or BSE ticker symbol"},
                    "exchange": {"type": "string", "enum": ["NSE", "BSE", "BSE_SME", ""]},
                    "node_role": {"type": "string", "enum": ["direct", "first_order", "second_order", "proxy"]},
                    "linkage_tightness": {"type": "string", "enum": ["tight", "moderate", "loose"]},
                    "linkage_explanation": {"type": "string", "description": "1-sentence causal link to the economic primitive"},
                    "liquidity_flag": {"type": "string", "enum": ["ok", "thin", "illiquid"]},
                    "coverage_gap": {"type": "string", "enum": ["hidden_gem", "under_covered", "well_covered"]},
                    "epistemic_tag": {"type": "string", "enum": ["V", "E", "I"]},
                },
                "required": ["company_name", "ticker", "exchange", "node_role",
                             "linkage_tightness", "linkage_explanation",
                             "liquidity_flag", "coverage_gap", "epistemic_tag"],
            },
        },
        "india_exposure_rating": {
            "type": "string",
            "enum": ["strong", "moderate", "thin", "none"],
            "description": "Overall assessment of India's exposure to this theme's economic primitive",
        },
        "india_exposure_note": {
            "type": "string",
            "description": "1-2 sentence honest assessment of India's exposure — be explicit if thin",
        },
    },
    "required": ["india_nodes", "india_exposure_rating", "india_exposure_note"],
}

_SYSTEM = (
    "You are an expert on Indian equity markets (NSE, BSE, SME boards) mapping Indian companies "
    "exposed to US investment themes via the underlying economic primitive. "
    "CRITICAL RULES:\n"
    "- Extract the ECONOMIC PRIMITIVE first (e.g. 'thermal management for >100kW racks'), not the US ticker\n"
    "- Map Indian companies to the PRIMITIVE, not the US theme name\n"
    "- Include BSE SME board hidden gems — surface under-covered names with genuine exposure\n"
    "- Always set linkage_tightness honestly — 'tight' only if revenue is directly tied\n"
    "- Default epistemic_tag='I' unless a hard catalyst (filing, concall) justifies V or E\n"
    "- Flag thin/illiquid stocks explicitly — a correct thesis in an untradeable stock is useless\n"
    "- If India has NO meaningful exposure, say so explicitly — do not invent connections"
)


def _build_prompt(theme_name: str, primitive: str, thesis: str, us_nodes: list[dict]) -> str:
    us_direct = [n for n in us_nodes if n.get("node_role") == "direct"]
    us_names = ", ".join(n.get("company_name", "") for n in us_direct[:3]) or "none identified"
    return (
        f"US Theme: {theme_name}\n"
        f"Economic primitive: {primitive}\n"
        f"What's happening now: {thesis}\n"
        f"Key US direct plays: {us_names}\n\n"
        f"Find Indian-listed companies (NSE/BSE/SME) exposed to the SAME economic primitive.\n"
        f"Reference example for calibration:\n"
        f"  US liquid-cooling theme → primitive 'high-density compute thermal management'\n"
        f"  → Aeroflex (flexible insulation/tubing for cooling loops, NSE, tight)\n"
        f"  → Supreme Industries (polymer pipe for HVAC/cooling, NSE, moderate)\n"
        f"  → Himadri Speciality Chemical (thermal interface materials, BSE, loose)\n\n"
        f"Follow this logic for the actual theme above. Include SME board names if genuinely exposed."
    )


def run_india_crossmap(theme_id: str) -> dict | None:
    """Run India cross-map for a theme. Returns dict with india_nodes + exposure rating."""
    provider = get_provider(get_value_chain_model())
    if not provider:
        log.debug("india_crossmap skipped — no model provider configured")
        return None

    theme = store.get_theme(theme_id)
    if not theme:
        return None

    analysis = store.get_theme_analysis(theme_id)
    if not analysis or not analysis.get("one_line_thesis"):
        log.debug("india_crossmap skipped — no synthesis for %s", theme_id)
        return None

    us_nodes = store.get_value_chain(theme_id)

    result = provider.structured_completion(
        system=_SYSTEM,
        user=_build_prompt(
            theme["name"],
            theme.get("primitive", ""),
            analysis["one_line_thesis"],
            us_nodes,
        ),
        tool_name=_TOOL_NAME,
        tool_description=_TOOL_DESCRIPTION,
        tool_schema=_TOOL_SCHEMA,
        max_tokens=2048,
    )
    if not result:
        return None

    # Persist india nodes into value_chain_nodes with a source='india' marker
    # We reuse value_chain_nodes but add exchange=NSE/BSE/BSE_SME to distinguish
    india_rows = []
    for n in result.get("india_nodes", []):
        exchange = n.get("exchange", "")
        if exchange not in ("NSE", "BSE", "BSE_SME", ""):
            continue  # skip US slippage
        india_rows.append({
            "theme_id": theme_id,
            "node_role": n.get("node_role", "proxy"),
            "ticker": n.get("ticker", ""),
            "exchange": exchange,
            "company_name": n.get("company_name", ""),
            "linkage_tightness": n.get("linkage_tightness", "loose"),
            "justification": n.get("linkage_explanation", ""),
            "liquidity_flag": n.get("liquidity_flag", "ok"),
            "epistemic_tag": n.get("epistemic_tag", "I"),
        })

    store.replace_india_crossmap(theme_id, india_rows)
    log.info("india_crossmap stored: %d nodes for %s (exposure: %s)",
             len(india_rows), theme_id, result.get("india_exposure_rating"))
    return result
