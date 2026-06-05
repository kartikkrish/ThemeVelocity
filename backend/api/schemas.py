"""FastAPI response schemas (Pydantic v2)."""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel


class ThemeHeat(BaseModel):
    theme_id: str
    name: str
    composite_score: float
    source_diversity: int
    earliness: float
    breaching: bool
    ts: str


class VelocityPoint(BaseModel):
    ts: str
    composite_score: float
    source_diversity: int
    earliness: float
    breaching: bool


class SourceSnapshot(BaseModel):
    source: str
    zscore: float
    cusum: float
    velocity: float
    acceleration: float
    count_1d: int


class ThemeDetail(BaseModel):
    theme_id: str
    name: str
    primitive: str | None
    status: str
    composite_score: float
    source_diversity: int
    earliness: float
    breaching: bool
    per_source: list[SourceSnapshot]
    velocity_history: list[VelocityPoint]


class AlertItem(BaseModel):
    alert_id: str
    theme_id: str
    fired_at: str
    composite_score: float
    acknowledged: bool


class IngestionStatus(BaseModel):
    status: str
    counts: dict[str, int]
