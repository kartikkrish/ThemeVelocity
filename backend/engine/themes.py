"""Theme lexicon registry + keyword-based tagger.

P1: pure keyword matching (no spaCy dependency at boot).
Each theme has seed keywords; text is matched via simple substring search
on lowercased tokens. Confidence is fraction of keywords matched.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import NamedTuple

from backend.db import store


# ---------------------------------------------------------------------------
# Seed theme definitions  (extend as themes emerge)
# ---------------------------------------------------------------------------
SEED_THEMES: list[dict] = [
    {
        "theme_id": "liquid_cooling",
        "name": "Data Center Liquid Cooling",
        "primitive": "thermal management hardware for >100kW compute racks",
        "keywords": [
            "liquid cooling", "direct liquid cooling", "immersion cooling",
            "cold plate", "coolant distribution unit", "CDU",
            "rear-door heat exchanger", "two-phase cooling", "data center cooling",
            "thermal management", "rack cooling", "server cooling",
        ],
        "status": "candidate",
    },
    {
        "theme_id": "cpo",
        "name": "Co-Packaged Optics",
        "primitive": "moving exabytes between GPU clusters at lower power per bit",
        "keywords": [
            "co-packaged optics", "CPO", "silicon photonics", "optical I/O",
            "photonic integrated circuit", "PIC", "optical interconnect",
            "pluggable optics", "800G", "1.6T transceiver", "coherent optics",
            "datacenter optics",
        ],
        "status": "candidate",
    },
    {
        "theme_id": "grid_transformers",
        "name": "Grid Transformer Shortage",
        "primitive": "high-voltage power transformation infrastructure bottleneck",
        "keywords": [
            "grid transformer", "power transformer", "substation",
            "transformer shortage", "transmission infrastructure",
            "high voltage transformer", "HV transformer", "grid upgrade",
            "electric grid", "power grid expansion", "HVDC",
        ],
        "status": "candidate",
    },
    {
        "theme_id": "ai_inference",
        "name": "AI Inference Infrastructure",
        "primitive": "compute + memory + interconnect for low-latency model serving at scale",
        "keywords": [
            "AI inference", "inference chip", "inference accelerator",
            "LLM inference", "model serving", "inference cluster",
            "inference optimization", "speculative decoding", "KV cache",
            "AI accelerator", "NPU", "inference at the edge",
        ],
        "status": "candidate",
    },
    {
        "theme_id": "nuclear_power",
        "name": "Nuclear Power Revival",
        "primitive": "carbon-free baseload electricity for hyperscaler and grid demand",
        "keywords": [
            "nuclear power", "small modular reactor", "SMR",
            "advanced nuclear", "nuclear renaissance", "nuclear energy",
            "fission", "nuclear plant", "uranium", "reactor",
            "nuclear data center", "Microsoft nuclear", "Google nuclear",
        ],
        "status": "candidate",
    },
    {
        "theme_id": "humanoid_robotics",
        "name": "Humanoid Robotics",
        "primitive": "general-purpose bipedal robots for manufacturing and logistics",
        "keywords": [
            "humanoid robot", "bipedal robot", "Optimus", "Figure AI",
            "1X Technologies", "Agility Robotics", "Boston Dynamics",
            "robot labor", "robotic workforce", "dexterous manipulation",
            "embodied AI", "robot arms", "actuator",
        ],
        "status": "candidate",
    },
    {
        "theme_id": "agentic_ai",
        "name": "Agentic AI / AI Agents",
        "primitive": "multi-step autonomous reasoning systems replacing white-collar workflows",
        "keywords": [
            "AI agent", "agentic AI", "autonomous agent", "multi-agent",
            "agent framework", "tool use", "function calling",
            "computer use", "browser agent", "coding agent",
            "MCP", "model context protocol", "workflow automation AI",
        ],
        "status": "candidate",
    },
    {
        "theme_id": "power_electronics",
        "name": "Wide-Bandgap Power Electronics",
        "primitive": "SiC/GaN semiconductor switching for EV and grid power conversion efficiency",
        "keywords": [
            "silicon carbide", "SiC", "gallium nitride", "GaN",
            "wide bandgap", "power electronics", "power semiconductor",
            "EV inverter", "onboard charger", "DC-DC converter",
            "power module", "MOSFET", "power device",
        ],
        "status": "candidate",
    },
]

# Early-source identifiers (used for earliness scoring)
EARLY_SOURCES = {"hn", "edgar", "arxiv"}
LATE_SOURCES = {"rss", "reuters", "bloomberg"}


@dataclass
class TagResult:
    theme_id: str
    confidence: float   # 0.0–1.0; fraction of keywords matched


class ThemeTagger:
    """Keyword-based theme tagger. Thread-safe (read-only after init)."""

    def __init__(self):
        self._themes: list[dict] = []
        self._patterns: dict[str, list[re.Pattern]] = {}

    def load(self) -> None:
        """Seed DB then load all themes + compile patterns."""
        self._seed_db()
        self._themes = store.get_all_themes()
        self._patterns = {}
        for t in self._themes:
            kws = json.loads(t["keywords"])
            self._patterns[t["theme_id"]] = [
                re.compile(r"\b" + re.escape(k.lower()) + r"\b") for k in kws
            ]

    def _seed_db(self) -> None:
        for td in SEED_THEMES:
            store.upsert_theme(
                {
                    "theme_id": td["theme_id"],
                    "name": td["name"],
                    "primitive": td.get("primitive", ""),
                    "keywords": json.dumps(td["keywords"]),
                    "status": td.get("status", "candidate"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

    def tag(self, text: str) -> list[TagResult]:
        """Return themes matched in `text`, sorted by confidence desc."""
        lower = text.lower()
        results: list[TagResult] = []
        for t in self._themes:
            tid = t["theme_id"]
            patterns = self._patterns.get(tid, [])
            if not patterns:
                continue
            matched = sum(1 for p in patterns if p.search(lower))
            if matched > 0:
                conf = matched / len(patterns)
                results.append(TagResult(theme_id=tid, confidence=conf))
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def get_all_keywords(self) -> list[str]:
        """Flat list of all keywords across all themes (for fetcher queries)."""
        out: list[str] = []
        for t in self._themes:
            out.extend(json.loads(t["keywords"]))
        return list(set(out))

    def top_query_terms(self, n: int = 20) -> list[str]:
        """Representative query terms for P1 fetchers (avoid overlong lists)."""
        # Prefer multi-word terms (more specific), dedup
        all_kw = self.get_all_keywords()
        multi = [k for k in all_kw if " " in k]
        single = [k for k in all_kw if " " not in k]
        combined = multi + single
        return list(dict.fromkeys(combined))[:n]   # preserve order, dedup


# Module-level singleton
tagger = ThemeTagger()
