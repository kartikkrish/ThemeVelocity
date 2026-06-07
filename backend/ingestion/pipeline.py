"""Ingestion pipeline: fetch → tag → store events → discovery cycle."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.db import store
from backend.engine.themes import tagger
from backend.engine.discovery import run_discovery_cycle
from backend.ingestion.edgar import EdgarFetcher
from backend.ingestion.gdelt import GDELTFetcher
from backend.ingestion.hn import HNFetcher, HNFirehoseFetcher
from backend.ingestion.ticker_extractor import extract_tickers

log = logging.getLogger(__name__)


def _build_keyword_fetchers(query_terms: list[str]) -> list:
    """Keyword-gated fetchers — reliable signal for known themes."""
    top = query_terms[:15]
    return [
        EdgarFetcher(query_terms=top),
        HNFetcher(query_terms=top),
        GDELTFetcher(query_terms=top),
    ]


def _build_discovery_fetchers() -> list:
    """Broad / firehose fetchers — no keyword filter, feeds open discovery."""
    return [
        HNFirehoseFetcher(),   # all recent HN stories, unfiltered
    ]


def run_ingestion(since: datetime, sources: list[str] | None = None) -> dict[str, int]:
    """Fetch from sources since `since`, tag, persist. sources=None runs all.

    After persisting events, runs the discovery cycle which extracts candidate
    phrases from all recent text and auto-promotes accelerating terms into the
    themes table — no LLM involved.

    Returns dict of {source: new_event_count}.
    """
    fetched_at = datetime.now(timezone.utc)
    query_terms = tagger.top_query_terms(n=15)

    # ── keyword-gated fetchers (known themes) ────────────────────────────
    all_kw_fetchers = _build_keyword_fetchers(query_terms)
    kw_fetchers = [f for f in all_kw_fetchers if sources is None or f.source in sources]

    # ── discovery fetchers (open vocabulary) ─────────────────────────────
    # Only run firehose when sources=None (full cycle) or explicitly requested
    disc_fetchers = _build_discovery_fetchers() if sources is None else []

    totals: dict[str, int] = {}

    for fetcher in kw_fetchers + disc_fetchers:
        try:
            events = fetcher.fetch(since=since)
            new_count = 0
            for ev in events:
                row = ev.to_db_row(fetched_at)
                is_new = store.upsert_event(row)
                if is_new:
                    # Tag against known-theme lexicon
                    tags = tagger.tag(ev.raw_text)
                    for tag in tags:
                        store.insert_event_theme(ev.event_id, tag.theme_id, tag.confidence)
                    for ticker, exchange in extract_tickers(ev.raw_text):
                        store.insert_event_entity(ev.event_id, ticker, "TICKER", ticker, exchange)
                    new_count += 1
            src_key = f"{fetcher.source}{'_firehose' if not hasattr(fetcher, '_query_terms') else ''}"
            totals[fetcher.source] = totals.get(fetcher.source, 0) + new_count
            log.info("ingestion %s: %d events fetched, %d new",
                     fetcher.source, len(events), new_count)
        except Exception as exc:
            log.error("ingestion error [%s]: %s", fetcher.source, exc)
            totals[fetcher.source] = totals.get(fetcher.source, -1)

    # ── discovery cycle: open-vocabulary term velocity + auto-promotion ───
    # Runs regardless of which sources were fetched — operates on the full
    # events table, not just what was fetched this run.
    try:
        new_themes = run_discovery_cycle()
        if new_themes:
            log.info("discovery: %d new candidate theme(s) registered", new_themes)
        totals["_discovered"] = new_themes
    except Exception as exc:
        log.error("discovery cycle error: %s", exc)

    return totals
