"""Regex + alias-map ticker/entity extraction (spaCy-free, Phase 1).

Extracts US and NSE/BSE tickers from raw text using:
  1. Explicit formats: $TICK, (NYSE: TICK), (NASDAQ: TICK), (NSE: TICK), etc.
  2. Curated company-name → ticker alias map for the 8 seed themes.
  3. Contextual ALLCAPS 2-5 char patterns filtered against a known-ticker set.

Returns list of (ticker, exchange) tuples, deduplicated.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Curated alias map — company name fragments (lowercase) → (ticker, exchange)
# Covers the 8 seed themes from themes.py
# ---------------------------------------------------------------------------
_ALIAS: dict[str, tuple[str, str]] = {
    # Liquid cooling / thermal management
    "vertiv": ("VRT", "NYSE"),
    "modine": ("MOD", "NYSE"),
    "aavid": ("BOYD", "NASDAQ"),    # Boyd Gaming acquired Aavid
    "boyd cooling": ("BOYD", "NASDAQ"),
    "aspen systems": ("ASPN", "NYSE"),
    "aspen aerogels": ("ASPN", "NYSE"),
    # CPO / co-packaged optics
    "intel": ("INTC", "NASDAQ"),
    "broadcom": ("AVGO", "NASDAQ"),
    "marvell": ("MRVL", "NASDAQ"),
    "coherent": ("COHR", "NYSE"),
    "ii-vi": ("COHR", "NYSE"),
    "lumentum": ("LITE", "NASDAQ"),
    "inphi": ("MRVL", "NASDAQ"),    # acquired by Marvell
    # Agentic AI / inference
    "nvidia": ("NVDA", "NASDAQ"),
    "amd": ("AMD", "NASDAQ"),
    "advanced micro devices": ("AMD", "NASDAQ"),
    "microsoft": ("MSFT", "NASDAQ"),
    "alphabet": ("GOOGL", "NASDAQ"),
    "google": ("GOOGL", "NASDAQ"),
    "meta platforms": ("META", "NASDAQ"),
    "qualcomm": ("QCOM", "NASDAQ"),
    "cerebras": ("CBRS", "NASDAQ"),
    "arm holdings": ("ARM", "NASDAQ"),
    # Nuclear
    "constellation energy": ("CEG", "NASDAQ"),
    "vistra": ("VST", "NYSE"),
    "cameco": ("CCJ", "NYSE"),
    "nuscale": ("SMR", "NYSE"),
    "uranium energy": ("UEC", "NYSEAMERICAN"),
    "denison mines": ("DNN", "NYSEAMERICAN"),
    "oklo": ("OKLO", "NYSE"),
    "kairos power": ("", ""),       # private
    # Grid transformers / power infrastructure
    "eaton": ("ETN", "NYSE"),
    "hubbell": ("HUBB", "NYSE"),
    "ge vernova": ("GEV", "NYSE"),
    "abb": ("ABB", "NYSE"),
    "roper technologies": ("ROP", "NASDAQ"),
    "acuity brands": ("AYI", "NYSE"),
    "preformed line": ("PLPC", "NASDAQ"),
    # Humanoid robotics
    "tesla": ("TSLA", "NASDAQ"),
    "boston dynamics": ("", ""),    # private (Hyundai)
    "apptronik": ("", ""),          # private
    "agility robotics": ("", ""),   # private
    "rainbow robotics": ("", ""),   # KRX
    "fanuc": ("FANUY", "OTC"),
    # Power electronics / SiC/GaN
    "on semiconductor": ("ON", "NASDAQ"),
    "onsemi": ("ON", "NASDAQ"),
    "wolfspeed": ("WOLF", "NYSE"),
    "infineon": ("IFNNY", "OTC"),
    "st microelectronics": ("STM", "NYSE"),
    "stmicroelectronics": ("STM", "NYSE"),
    "monolithic power": ("MPWR", "NASDAQ"),
    "power integrations": ("POWI", "NASDAQ"),
    # India — liquid cooling / thermal
    "aeroflex": ("AEROFLEX", "NSE"),
    "apar industries": ("APARINDS", "NSE"),
    # India — power / grid
    "bharat heavy": ("BHEL", "NSE"),
    "bhel": ("BHEL", "NSE"),
    "siemens india": ("SIEMENS", "NSE"),
    "abb india": ("ABB", "NSE"),
    "hitachi energy": ("POWERINDIA", "NSE"),
    "transformer and rectifier": ("TARIL", "NSE"),
    # India — power electronics / semiconductors
    "bharat electronics": ("BEL", "NSE"),
    "dixon technologies": ("DIXON", "NSE"),
    "kaynes technology": ("KAYNES", "NSE"),
}

# ---------------------------------------------------------------------------
# Known US exchange prefixes in text
# ---------------------------------------------------------------------------
_EXCHANGE_PATTERN = re.compile(
    r"\((?:NYSE|NASDAQ|NYSEAMERICAN|AMEX|OTC)[:\s]+([A-Z]{1,5})\)",
    re.IGNORECASE,
)
# India exchange references
_INDIA_EXCHANGE_PATTERN = re.compile(
    r"\((?:NSE|BSE)[:\s]+([A-Z0-9]{2,20})\)",
    re.IGNORECASE,
)
# $TICK format
_DOLLAR_TICK = re.compile(r"\$([A-Z]{1,5})\b")

# Standalone ALLCAPS 2-5 chars surrounded by non-alpha (noise-prone, used as fallback)
_ALLCAPS = re.compile(r"(?<![A-Z])([A-Z]{2,5})(?![A-Z])")
# Stopwords to reject from ALLCAPS matches
_ALLCAPS_STOP = frozenset({
    "A", "AI", "AM", "AN", "AS", "AT", "BE", "BY", "CEO", "CFO", "COO",
    "CTO", "DO", "EV", "FOR", "FROM", "GPU", "HPC", "IN", "IP", "IS", "IT",
    "ML", "MM", "NO", "OF", "ON", "OR", "PC", "PR", "R&D", "RE", "RF",
    "THE", "TO", "TV", "US", "USD", "VR", "XR",
})


def extract_tickers(text: str) -> list[tuple[str, str]]:
    """Return deduplicated [(ticker, exchange)] from text."""
    results: dict[str, str] = {}  # ticker → exchange

    # 1. Explicit exchange references
    for m in _EXCHANGE_PATTERN.finditer(text):
        results[m.group(1).upper()] = m.group(0)[1:m.group(0).index(":")].upper().strip("(")
    for m in _INDIA_EXCHANGE_PATTERN.finditer(text):
        results[m.group(1).upper()] = m.group(0)[1:m.group(0).index(":")].upper().strip("(")

    # 2. $TICK references
    for m in _DOLLAR_TICK.finditer(text):
        tick = m.group(1).upper()
        if tick not in results:
            results[tick] = "US"

    # 3. Alias map lookup on lowercased text
    lower = text.lower()
    for alias, (ticker, exchange) in _ALIAS.items():
        if ticker and alias in lower and ticker not in results:
            results[ticker] = exchange

    # Filter out empty tickers (private companies in map)
    return [(t, e) for t, e in results.items() if t]
