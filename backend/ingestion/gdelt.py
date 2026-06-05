"""GDELT 2.0 Doc API fetcher.

Doc API: https://api.gdeltproject.org/api/v2/doc/doc
No auth required. 15-min update cadence.
Returns article counts and timeline data for theme terms.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import requests

from backend.ingestion.base import Fetcher, RawEvent

log = logging.getLogger(__name__)
GDELT_DOC = "https://api.gdeltproject.org/api/v2/doc/doc"


class GDELTFetcher(Fetcher):
    source = "gdelt"
    source_weight = 0.6

    def __init__(self, query_terms: list[str] | None = None):
        self._session = requests.Session()
        self._query_terms = query_terms or []

    def fetch(self, since: datetime) -> list[RawEvent]:
        events: list[RawEvent] = []
        for term in self._query_terms:
            try:
                events.extend(self._fetch_term(term, since))
                time.sleep(0.5)   # GDELT asks for polite access
            except Exception as exc:
                log.warning("GDELT fetch failed for term=%r: %s", term, exc)
        return events

    def _fetch_term(self, term: str, since: datetime) -> list[RawEvent]:
        # Use artlist mode: returns list of articles matching query
        params = {
            "query": term,
            "mode": "artlist",
            "maxrecords": 75,
            "format": "json",
            "startdatetime": since.strftime("%Y%m%d%H%M%S"),
            "enddatetime": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "sort": "DateDesc",
        }
        resp = self._session.get(GDELT_DOC, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        articles = data.get("articles", [])
        results: list[RawEvent] = []
        for art in articles:
            url = art.get("url", "")
            title = art.get("title", "")
            seendate = art.get("seendate", "")
            if not seendate or not url:
                continue
            try:
                pub = datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            results.append(
                RawEvent(
                    source=self.source,
                    source_weight=self.source_weight,
                    published_at=pub,
                    raw_text=title[:2000],
                    url=url,
                )
            )
        return results
