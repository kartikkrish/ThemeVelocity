"""Hacker News Algolia API fetcher (hn.algolia.com/api/v1).

No auth required. Real-time. Leading deep-tech signal.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

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
HN_SEARCH = "https://hn.algolia.com/api/v1/search_by_date"


class HNFetcher(Fetcher):
    source = "hn"
    source_weight = 0.7

    def __init__(self, query_terms: list[str] | None = None):
        self._session = _session_with_retry()
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
            "tags": "(story,comment)",   # parens = OR; "story,comment" means AND -> always empty
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


class HNFirehoseFetcher(Fetcher):
    """Fetches ALL recent HN stories — no keyword filter.

    Used by the discovery engine so that emerging topics that are not yet
    in the seed lexicon can be detected and auto-promoted.
    """
    source = "hn"
    source_weight = 0.7

    def __init__(self):
        self._session = _session_with_retry()

    def fetch(self, since: datetime) -> list[RawEvent]:
        since_ts = int(since.timestamp())
        params = {
            "tags": "story",
            "numericFilters": f"created_at_i>{since_ts}",
            "hitsPerPage": 200,
        }
        try:
            resp = self._session.get(HN_SEARCH, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            log.warning("HN firehose fetch failed: %s", exc)
            return []

        results: list[RawEvent] = []
        for hit in data.get("hits", []):
            ts_i = hit.get("created_at_i", 0)
            if not ts_i:
                continue
            pub = datetime.fromtimestamp(ts_i, tz=timezone.utc)
            title = hit.get("title") or ""
            if not title:
                continue
            story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID','')}"
            obj_id = hit.get("objectID", "")
            results.append(RawEvent(
                source=self.source,
                source_weight=self.source_weight,
                published_at=pub,
                raw_text=title[:2000],
                url=story_url,
                event_id=f"hn_{obj_id}",
            ))
        return results


def hn_backfill_term_counts(term: str, days: int = 90) -> dict[str, int]:
    """Fetch daily mention counts for `term` over the last `days` days from HN.

    Uses the Algolia search_by_date API with pagination to collect all hits,
    then groups by calendar day. Returns {YYYY-MM-DD: count}.

    Called by the discovery engine when a term is first seen so it can
    immediately compute a Z-score against a real 90-day baseline instead of
    waiting days for counts to accumulate organically.
    """
    session = _session_with_retry()
    now = datetime.now(timezone.utc)
    since_ts = int((now - timedelta(days=days)).timestamp())

    daily: dict[str, int] = defaultdict(int)
    page = 0
    while True:
        try:
            resp = session.get(HN_SEARCH, params={
                "query": term,
                "tags": "story",
                "numericFilters": f"created_at_i>{since_ts}",
                "hitsPerPage": 1000,
                "page": page,
            }, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            log.warning("HN backfill failed term=%r page=%d: %s", term, page, exc)
            break

        hits = data.get("hits", [])
        for hit in hits:
            ts_i = hit.get("created_at_i", 0)
            if ts_i:
                day = datetime.fromtimestamp(ts_i, tz=timezone.utc).strftime("%Y-%m-%d")
                daily[day] += 1

        nb_pages = data.get("nbPages", 1)
        page += 1
        if page >= nb_pages or page >= 10:   # cap at 10 pages to avoid runaway
            break
        time.sleep(0.2)

    log.info("HN backfill term=%r days=%d: %d days with mentions", term, days, len(daily))
    return dict(daily)
