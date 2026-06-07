"""Theme tagger — keyword-based matching against DB-resident themes.

No hardcoded seed lexicon. Themes enter the DB exclusively via the
discovery engine (HN firehose → term velocity → auto-promotion).
EDGAR and GDELT are then queried with the keywords of whatever themes
exist in the DB, closing the discovery → multi-source signal loop.

Cold-start behaviour: on day 1 the DB is empty, so only the HN
firehose runs. Candidates appear within a few days; EDGAR/GDELT
queries are added automatically on the next ingestion cycle.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from backend.db import store

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
        """Load all themes from DB and compile keyword patterns."""
        self._themes = store.get_all_themes()
        self._patterns = {}
        for t in self._themes:
            kws = json.loads(t["keywords"])
            self._patterns[t["theme_id"]] = [
                re.compile(r"\b" + re.escape(k.lower()) + r"\b") for k in kws
            ]

    # Alias so callers can reload after discovery promotes new candidates
    reload = load

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
