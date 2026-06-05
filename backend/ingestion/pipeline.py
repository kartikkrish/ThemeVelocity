"""Ingestion pipeline: fetch → tag → store events."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.db import store
from backend.engine.themes import tagger
from backend.ingestion.edgar import EdgarFetcher
from backend.ingestion.gdelt import GDELTFetcher
from backend.ingestion.hn import HNFetcher

log = logging.getLogger(__name__)


def _build_fetchers(query_terms: list[str]) -> list:
    # Use top 15 terms per fetcher to stay polite on rate limits
    top = query_terms[:15]
    return [
        EdgarFetcher(query_terms=top),
        HNFetcher(query_terms=top),
        GDELTFetcher(query_terms=top),
    ]


def run_ingestion(since: datetime) -> dict[str, int]:
    """Fetch from all sources since `since`, tag, persist. Returns counts."""
    fetched_at = datetime.now(timezone.utc)
    query_terms = tagger.top_query_terms(n=15)
    fetchers = _build_fetchers(query_terms)

    totals: dict[str, int] = {}
    for fetcher in fetchers:
        try:
            events = fetcher.fetch(since=since)
            new_count = 0
            for ev in events:
                row = ev.to_db_row(fetched_at)
                is_new = store.upsert_event(row)
                if is_new:
                    # Tag against theme lexicon
                    tags = tagger.tag(ev.raw_text)
                    for tag in tags:
                        store.insert_event_theme(ev.event_id, tag.theme_id, tag.confidence)
                    new_count += 1
            totals[fetcher.source] = new_count
            log.info("ingestion %s: %d events fetched, %d new", fetcher.source, len(events), new_count)
        except Exception as exc:
            log.error("ingestion error [%s]: %s", fetcher.source, exc)
            totals[fetcher.source] = -1   # signal failure

    return totals
