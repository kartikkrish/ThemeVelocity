"""Velocity engine — the heart of Phase 1.

Computes per-theme×source:
  • rolling mention counts (1d / 7d / 30d / 90d)
  • first derivative (velocity) and second derivative (acceleration)
  • Z-score vs trailing baseline
  • CUSUM structural-break statistic

Then combines into a composite 0–100 signal with source-diversity weighting
and an earliness estimate.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import numpy as np

from backend import config
from backend.db import store

log = logging.getLogger(__name__)

SOURCES = ["edgar", "hn", "gdelt"]
SOURCE_WEIGHTS: dict[str, float] = {
    "edgar": 1.0,
    "hn": 0.7,
    "gdelt": 0.6,
}
EARLY_SOURCES = {"edgar", "hn"}   # high earliness weight
LATE_SOURCES = {"gdelt"}           # mainstream proxy


class VelocityResult(NamedTuple):
    theme_id: str
    composite_score: float      # 0–100
    source_diversity: int       # # source types breaching
    earliness: float            # 0–1
    breaching: bool
    per_source: dict            # source -> {zscore, cusum, velocity, acceleration}


def _cusum(series: np.ndarray, k: float, h: float) -> float:
    """Page's CUSUM — returns latest S+ statistic."""
    if len(series) < 4:
        return 0.0
    mu = np.mean(series[:-1])
    sigma = np.std(series[:-1]) or 1.0
    normalized = (series - mu) / sigma
    S = 0.0
    for x in normalized:
        S = max(0.0, S + x - k)
    return float(S)


def _zscore(series: np.ndarray) -> float:
    """Z-score of last value vs series mean/std."""
    if len(series) < 4:
        return 0.0
    mu = np.mean(series[:-1])
    sigma = np.std(series[:-1]) or 1.0
    return float((series[-1] - mu) / sigma)


def _derivative(series: np.ndarray) -> tuple[float, float]:
    """First and second derivatives of last point."""
    if len(series) < 2:
        return 0.0, 0.0
    vel = float(series[-1] - series[-2])
    acc = float(series[-1] - 2 * series[-2] + series[-3]) if len(series) >= 3 else 0.0
    return vel, acc


def compute_theme_velocity(theme_id: str, now: datetime | None = None) -> VelocityResult:
    now = now or datetime.now(timezone.utc)
    baseline_since = now - timedelta(days=config.BASELINE_DAYS)

    per_source: dict = {}
    source_scores: list[float] = []
    breaching_sources: set[str] = set()
    early_mentions = 0
    late_mentions = 0

    for src in SOURCES:
        ts_data = store.get_mention_timeseries(theme_id, src, baseline_since)
        if not ts_data:
            per_source[src] = {"zscore": 0.0, "cusum": 0.0, "velocity": 0.0, "acceleration": 0.0, "count_1d": 0}
            continue

        # Build daily count array (fill missing days with 0)
        day_map = {r["day"]: r["count"] for r in ts_data}
        all_days = [(baseline_since + timedelta(days=i)).strftime("%Y-%m-%d")
                    for i in range(config.BASELINE_DAYS + 1)]
        counts = np.array([float(day_map.get(d, 0)) for d in all_days])

        z = _zscore(counts)
        cusum_val = _cusum(counts, k=config.CUSUM_K, h=config.CUSUM_H)
        vel, acc = _derivative(counts)
        count_1d = int(counts[-1])

        # Persist snapshot
        store.upsert_velocity_snapshot({
            "theme_id": theme_id,
            "source": src,
            "window_days": 1,
            "ts": now.isoformat(),
            "mention_count": count_1d,
            "velocity": vel,
            "acceleration": acc,
            "zscore": z,
            "cusum": cusum_val,
        })

        per_source[src] = {
            "zscore": z,
            "cusum": cusum_val,
            "velocity": vel,
            "acceleration": acc,
            "count_1d": count_1d,
        }

        # Source-level breach: Z > threshold OR CUSUM > H
        breaching = z >= config.VELOCITY_Z_THRESHOLD or cusum_val >= config.CUSUM_H
        if breaching:
            breaching_sources.add(src)

        w = SOURCE_WEIGHTS.get(src, 0.5)
        # Normalize Z to 0–1 contribution, weight by source quality
        z_contrib = min(max(z, 0.0), 5.0) / 5.0   # clamp Z to [0,5], normalize
        source_scores.append(z_contrib * w)

        # Earliness: track early vs late mention volumes
        if src in EARLY_SOURCES:
            early_mentions += count_1d
        if src in LATE_SOURCES:
            late_mentions += count_1d

    # Composite 0–100
    if source_scores:
        raw = np.mean(source_scores)          # 0–1 weighted avg
        diversity_bonus = min(len(breaching_sources) / len(SOURCES), 1.0) * 0.3
        composite = min((raw + diversity_bonus) * 100, 100.0)
    else:
        composite = 0.0

    # Earliness: ratio of early mentions to total
    total_mentions = early_mentions + late_mentions
    earliness = (early_mentions / total_mentions) if total_mentions > 0 else 0.5

    # Composite breach: diversity requirement
    breaching = (
        len(breaching_sources) >= config.DIVERSITY_MIN_SOURCES
        or (len(breaching_sources) >= 1 and composite >= 50)
    )

    result = VelocityResult(
        theme_id=theme_id,
        composite_score=round(composite, 2),
        source_diversity=len(breaching_sources),
        earliness=round(earliness, 3),
        breaching=breaching,
        per_source=per_source,
    )

    store.upsert_composite({
        "theme_id": theme_id,
        "ts": now.isoformat(),
        "composite_score": result.composite_score,
        "source_diversity": result.source_diversity,
        "earliness": result.earliness,
        "breaching": int(result.breaching),
    })

    return result


def run_velocity_cycle(theme_ids: list[str] | None = None) -> list[VelocityResult]:
    """Run velocity computation for all (or specified) themes."""
    themes = store.get_all_themes()
    target_ids = set(theme_ids) if theme_ids else {t["theme_id"] for t in themes}
    results: list[VelocityResult] = []
    now = datetime.now(timezone.utc)
    for t in themes:
        if t["theme_id"] not in target_ids:
            continue
        try:
            r = compute_theme_velocity(t["theme_id"], now=now)
            results.append(r)
            log.debug("velocity %s: score=%.1f breach=%s", t["theme_id"], r.composite_score, r.breaching)
        except Exception as exc:
            log.error("velocity error for %s: %s", t["theme_id"], exc)
    return results
