"""Common Fetcher interface and RawEvent schema."""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawEvent:
    source: str
    source_weight: float
    published_at: datetime
    raw_text: str
    url: str
    event_id: str = field(default="")

    def __post_init__(self):
        if not self.event_id:
            blob = f"{self.source}|{self.url}|{self.published_at.isoformat()}"
            self.event_id = hashlib.sha1(blob.encode()).hexdigest()[:20]

    def to_db_row(self, fetched_at: datetime) -> dict:
        return {
            "event_id": self.event_id,
            "source": self.source,
            "source_weight": self.source_weight,
            "published_at": self.published_at.isoformat(),
            "fetched_at": fetched_at.isoformat(),
            "raw_text": self.raw_text,
            "url": self.url,
            "syndication_count": 1,
        }


class Fetcher(ABC):
    source: str
    source_weight: float

    @abstractmethod
    def fetch(self, since: datetime) -> list[RawEvent]:
        """Fetch events published after `since`."""
        ...
