"""6-component confidence scorer (FR-CONF-1 through FR-CONF-5).

Components:
  1  Velocity strength   0–25   quant — magnitude of Z-score / acceleration
  2  Source quality      0–20   quant — weighted breadth of independent sources
  3  Catalyst concreteness 0–20 LLM-judged — hard catalyst vs pure narrative
  4  Earliness           0–15   quant — inverse mainstream penetration
  5  Linkage tightness   0–10   stub Phase 3 (neutral 5 until value-chain data)
  6  Liquidity           0–10   stub Phase 3 (neutral 7 until price/volume data)
  Total: 0–100
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConfidenceScore:
    c_velocity: float     # 0–25
    c_source: float       # 0–20
    c_catalyst: float     # 0–20
    c_earliness: float    # 0–15
    c_linkage: float      # 0–10
    c_liquidity: float    # 0–10
    c_total: float        # 0–100
    epistemic_tag: str    # V / E / I


_CATALYST_SCORES: dict[str, float] = {
    "earnings_guidance": 20.0,
    "order_flow":        18.0,
    "product_launch":    16.0,
    "regulatory_change": 15.0,
    "tech_breakthrough": 14.0,
    "macro_shift":       10.0,
    "pure_narrative":     4.0,
}

# Human-readable labels for the UI (key → (short label, description))
CATALYST_LABELS: dict[str, tuple[str, str]] = {
    "earnings_guidance":  ("Earnings Guidance",    "Companies are raising guidance or mentioning this theme in earnings calls"),
    "order_flow":         ("Order Activity",        "Concrete orders, backlog expansion, or lead-time changes observed"),
    "product_launch":     ("Product Launch",        "New product or major upgrade announced by key players"),
    "regulatory_change":  ("Regulatory Shift",      "Policy, regulation, or government mandate driving adoption"),
    "tech_breakthrough":  ("Tech Breakthrough",     "Meaningful technology advance shifting what's possible"),
    "macro_shift":        ("Macro Shift",           "Broad economic or structural change creating tailwinds"),
    "pure_narrative":     ("Narrative-Driven",      "Primarily conversation-driven — watch for hard catalyst confirmation"),
}

MATURITY_LABELS: dict[str, tuple[str, str, str]] = {
    "early_discovery":   ("Early Discovery",   "🔍", "Specialists are talking. Mainstream hasn't noticed yet."),
    "building_momentum": ("Building Momentum", "📈", "Theme is accelerating. Starting to gain wider attention."),
    "mainstream_known":  ("Widely Covered",    "📰", "Well-known theme. Less informational edge."),
}


def compute_confidence(velocity_result, synthesis: dict | None, value_chain_count: int = 0) -> ConfidenceScore:
    # 1. Velocity strength (0–25)
    c_velocity = round(min(velocity_result.composite_score / 100 * 25, 25.0), 1)

    # 2. Source quality & diversity (0–20): max when all 3 sources breach
    diversity_ratio = velocity_result.source_diversity / 3.0
    c_source = round(min(diversity_ratio * 20, 20.0), 1)

    # 3. Catalyst concreteness (0–20): from LLM synthesis
    catalyst_type = synthesis.get("catalyst_type", "pure_narrative") if synthesis else "pure_narrative"
    c_catalyst = _CATALYST_SCORES.get(catalyst_type, 8.0)
    if synthesis and not synthesis.get("is_real_theme", True):
        c_catalyst = max(c_catalyst - 12.0, 0.0)

    # 4. Earliness (0–15)
    c_earliness = round(min(velocity_result.earliness * 15, 15.0), 1)

    # 5. Linkage tightness (0–10) — stub until Phase 3 value-chain data
    c_linkage = 6.0 if value_chain_count >= 3 else (5.0 if value_chain_count > 0 else 3.0)

    # 6. Liquidity/tradability (0–10) — stub Phase 3
    c_liquidity = 7.0

    c_total = round(min(c_velocity + c_source + c_catalyst + c_earliness + c_linkage + c_liquidity, 100.0), 1)

    # Epistemic tag: weakest critical input dominates.
    # `or "I"` (not .get default) because models may return an explicit null.
    epis = (synthesis.get("epistemic_tag") if synthesis else None) or "I"

    return ConfidenceScore(
        c_velocity=c_velocity,
        c_source=c_source,
        c_catalyst=c_catalyst,
        c_earliness=c_earliness,
        c_linkage=c_linkage,
        c_liquidity=c_liquidity,
        c_total=c_total,
        epistemic_tag=epis,
    )
