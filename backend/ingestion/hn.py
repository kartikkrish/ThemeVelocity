"""Hacker News Algolia API fetcher (hn.algolia.com/api/v1).

No auth required. Real-time. Leading deep-tech signal.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

from backend.ingestion.base import Fetcher, RawEvent

log = logging.getLogger(__name__)
HN_SEARCH = "https://hn.algolia.com/api/v1/search_by_date"


class HNFetcher(Fetcher):
    source = "hn"
    source_weight = 0.7

    def __init__(self, query_terms: list[str] | None = None):
        self._session = requests.Session()
        self._query_terms = query_terms or []

    def fetch(self, since: datetime) -> list[RawEvent]:
        events: list[RawEvent] = []
        ts = int(since.timestamp())
        for term in self._query_terms:
            try:
                events.extend(self._fetch_term(term, ts))
                time.sleep(0.15)
            except Exception as exc:
                log.warning("HN fetch failed for term=%r: %s", term, exc)
        return events

    def _fetch_term(self, term: str, since_ts: int) -> list[RawEvent]:
        params = {
            "query": term,
            "numericFilters": f"created_at_i>{since_ts}",
            "hitsPerPage": 50,
            "tags": "story,comment",
        }
        resp = self._session.get(HN_SEARCH, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results: list[RawEvent] = []
        for hit in data.get("hits", []):
            ts_i = hit.get("created_at_i", 0)
            if ts_i == 0:
                continue
            pub = datetime.fromtimestamp(ts_i, tz=timezone.utc)
            title = hit.get("title") or hit.get("comment_text") or ""
            story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID','')}"
            obj_id = hit.get("objectID", "")
            results.append(
                RawEvent(
                    source=self.source,
                    source_weight=self.source_weight,
                    published_at=pub,
                    raw_text=title[:2000],
                    url=story_url,
                    event_id=f"hn_{obj_id}",
                )
            )
        return results
