"""Discovery engine — LLM-free open-vocabulary theme detection.

Every ingestion run:
  1. Extracts candidate phrases from all events published in the last 48 h.
  2. Counts phrase occurrences per (term × source × day) → term_counts table.
  3. Computes Z-score per (term × source) against a trailing baseline.
  4. When a term breaches Z ≥ BREACH_ZSCORE across ≥ MIN_SOURCES independent
     sources on ≥ MIN_DAYS different days, it is auto-registered as a new
     theme (status='candidate') in the themes table.
  5. The existing velocity engine then picks it up like any other theme.

No LLM involved — discovery is purely statistical.
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np

from backend.db import store
from backend.engine.term_extractor import extract_phrases

log = logging.getLogger(__name__)

# ── promotion thresholds ──────────────────────────────────────────────────
_BREACH_ZSCORE   = 2.0   # Z-score to count as "breaching"
_MIN_SOURCES     = 2     # independent sources both breaching
_MIN_DAYS        = 2     # distinct breach days required (anti-spike filter)
_MIN_TOTAL       = 5     # minimum total mentions across all history
_BASELINE_DAYS   = 21    # lookback for baseline mean/std
_RECENT_DAYS     = 7     # window treated as "recent" vs baseline
_MAX_NEW_PER_RUN = 15    # cap new registrations per cycle
_PROCESS_HOURS   = 48    # re-process events from this many hours back


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s[:64]


def run_discovery_cycle() -> int:
    """
    Extract terms from recent events, update term_counts, promote
    qualifying terms to the themes table.

    Returns number of newly registered candidate themes.
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=_PROCESS_HOURS)

    # ── 1. load recent events ─────────────────────────────────────────────
    events = store.get_events_since_published(since)
    if not events:
        log.debug("discovery: no events since %s", since.isoformat())
        return 0

    # ── 2. count phrases per (term, source, day) ──────────────────────────
    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    for ev in events:
        text = ev.get("raw_text") or ""
        if not text:
            continue
        day = ev["published_at"][:10]   # YYYY-MM-DD
        src = ev["source"]
        for phrase in extract_phrases(text):
            counts[(phrase, src, day)] += 1

    # ── 3. persist (replace counts for these days, don't accumulate) ──────
    store.replace_term_counts(list(counts.items()))
    log.info("discovery: stored %d term×source×day entries from %d events",
             len(counts), len(events))

    # ── 4. candidate terms: seen in ≥ MIN_SOURCES, ≥ MIN_TOTAL mentions ───
    lookback = _BASELINE_DAYS + _RECENT_DAYS
    candidates = store.get_term_candidates(
        min_sources=_MIN_SOURCES,
        min_total=_MIN_TOTAL,
        since_days=lookback,
    )

    # ── 5. skip already-registered slugs ─────────────────────────────────
    existing_slugs = {t["theme_id"] for t in store.get_all_themes()}

    new_count = 0
    for term in candidates:
        if new_count >= _MAX_NEW_PER_RUN:
            break
        slug = _slugify(term)
        if slug in existing_slugs:
            continue

        # ── 6. velocity check per source ─────────────────────────────────
        breach_sources: list[str] = []
        breach_days: set[str] = set()

        for src in store.get_term_sources(term):
            history = store.get_term_history(term, src, since_days=lookback)
            if len(history) < 5:
                continue

            days_arr  = [h["day"]   for h in history]
            count_arr = np.array([h["count"] for h in history], dtype=float)

            # split baseline vs recent
            split = max(len(count_arr) - _RECENT_DAYS, 3)
            baseline = count_arr[:split]
            recent   = count_arr[split:]
            recent_days = days_arr[split:]

            if len(baseline) < 3 or len(recent) == 0:
                continue

            mu    = baseline.mean()
            sigma = max(baseline.std(), 0.5)   # regularise — avoid ÷0
            z_recent = (recent - mu) / sigma

            if z_recent.max() >= _BREACH_ZSCORE:
                breach_sources.append(src)
                for day, z in zip(recent_days, z_recent):
                    if z >= _BREACH_ZSCORE:
                        breach_days.add(day)

        # ── 7. promote if multi-source + sustained ────────────────────────
        if len(breach_sources) >= _MIN_SOURCES and len(breach_days) >= _MIN_DAYS:
            log.info(
                "discovery: promoting %r  sources=%s  breach_days=%d",
                term, breach_sources, len(breach_days),
            )
            # Store the term plus any known co-occurring sub-phrases as keywords
            # so EDGAR/GDELT get useful query strings on the next ingestion cycle.
            kw_set: list[str] = [term]
            words = term.split()
            if len(words) >= 2:
                # Include each individual word as a fallback query term
                kw_set.extend(w for w in words if len(w) > 3)
            store.upsert_theme({
                "theme_id":   slug,
                "name":       term.title(),
                "primitive":  f"Auto-discovered via HN velocity — breach on {', '.join(breach_sources)}",
                "keywords":   json.dumps(list(dict.fromkeys(kw_set))),
                "status":     "candidate",
                "created_at": now.isoformat(),
            })
            existing_slugs.add(slug)
            new_count += 1

    if new_count:
        log.info("discovery: %d new candidate theme(s) registered", new_count)
    return new_count
