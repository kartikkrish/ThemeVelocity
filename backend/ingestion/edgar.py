"""SEC EDGAR full-text search fetcher (efts.sec.gov).

EDGAR full-text search covers 8-K, 10-Q, 10-K, S-1, etc.
We query the /efts/v1/simple endpoint — no API key required.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.ingestion.base import Fetcher, RawEvent


def _session_with_retry() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=4, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://",  HTTPAdapter(max_retries=retry))
    return s

log = logging.getLogger(__name__)

EDGAR_EFTS = "https://efts.sec.gov/LATEST/search-index?q={query}&dateRange=custom&startdt={start}&enddt={end}&_source=period_of_report,entity_name,file_date,form_type,period_of_report&hits.hits.total.value=true&hits.hits._source.period_of_report=true"
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"


class EdgarFetcher(Fetcher):
    source = "edgar"
    source_weight = 1.0

    def __init__(self, query_terms: list[str] | None = None):
        self._session = _session_with_retry()
        self._session.headers["User-Agent"] = "ThemeVelocity/1.0 kartik.krish@gmail.com"
        self._query_terms = query_terms or []

    def fetch(self, since: datetime) -> list[RawEvent]:
        events: list[RawEvent] = []
        now = datetime.now(timezone.utc)
        start_str = since.strftime("%Y-%m-%d")
        end_str = now.strftime("%Y-%m-%d")

        for term in self._query_terms:
            try:
                events.extend(self._fetch_term(term, start_str, end_str))
                time.sleep(0.2)   # polite rate-limit
            except Exception as exc:
                log.warning("EDGAR fetch failed for term=%r: %s", term, exc)

        return events

    def _fetch_term(self, term: str, start: str, end: str) -> list[RawEvent]:
        params = {
            "q": f'"{term}"',
            "dateRange": "custom",
            "startdt": start,
            "enddt": end,
            "hits.hits._source.period_of_report": "true",
        }
        resp = self._session.get(
            "https://efts.sec.gov/LATEST/search-index",
            params=params,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("hits", {}).get("hits", [])

        results: list[RawEvent] = []
        for h in hits:
            src = h.get("_source", {})
            file_date = src.get("file_date") or src.get("period_of_report")
            if not file_date:
                continue
            try:
                pub = datetime.fromisoformat(file_date).replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            entity = src.get("entity_name", "")
            form = src.get("form_type", "")
            excerpt = src.get("file_date", "")
            text = f"{entity} | {form} | mentions: {term}"
            url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={entity}&type={form}&dateb=&owner=include&count=10"
            hit_id = h.get("_id", "")

            results.append(
                RawEvent(
                    source=self.source,
                    source_weight=self.source_weight,
                    published_at=pub,
                    raw_text=text,
                    url=url,
                    event_id=f"edgar_{hit_id}" if hit_id else "",
                )
            )
        return results
