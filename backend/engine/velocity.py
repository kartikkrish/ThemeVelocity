"""Velocity engine — the heart of Phase 1.

Computes per-theme×source for each rolling window (1d / 7d / 30d / 90d):
  • rolling mention counts (FR-VEL-1)
  • first derivative (velocity) and second derivative (acceleration) (FR-VEL-2)
  • Z-score vs per-window baseline (30/60/90-day) (FR-VEL-3)
  • CUSUM structural-break statistic (FR-VEL-4)

Then combines into a composite 0–100 signal with source-diversity weighting
and an earliness estimate (FR-VEL-5, FR-VEL-6, FR-VEL-7, FR-VEL-8).
"""
from __future__ import annotations

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
EARLY_SOURCES = {"edgar", "hn"}
LATE_SOURCES = {"gdelt"}

# window_days → baseline_days for Z-score (FR-VEL-3: 30/60/90-day baselines)
WINDOW_BASELINES: dict[int, int] = config.WINDOW_BASELINES  # {1:30, 7:60, 30:90}
COMPOSITE_WINDOW = config.COMPOSITE_WINDOW  # 1-day: most sensitive to acceleration


class VelocityResult(NamedTuple):
    theme_id: str
    composite_score: float      # 0–100
    source_diversity: int       # # source types breaching
    earliness: float            # 0–1
    breaching: bool
    per_source: dict            # source -> {zscore, cusum, velocity, acceleration, count_1d}


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


def _rolling_sums(daily_counts: np.ndarray, window: int) -> np.ndarray:
    """Sliding window sums of length `window` over `daily_counts`."""
    n = len(daily_counts)
    return np.array([
        float(np.sum(daily_counts[max(0, i - window + 1):i + 1]))
        for i in range(n)
    ])


def compute_theme_velocity(theme_id: str, now: datetime | None = None) -> VelocityResult:
    now = now or datetime.now(timezone.utc)
    # Fetch enough history for the longest baseline (90d window needs 90d baseline)
    max_days = max(WINDOW_BASELINES.values()) + max(WINDOW_BASELINES.keys())
    baseline_since = now - timedelta(days=max_days)

    per_source: dict = {}
    source_scores: list[float] = []
    breaching_sources: set[str] = set()
    early_mentions = 0
    late_mentions = 0

    for src in SOURCES:
        ts_data = store.get_mention_timeseries(theme_id, src, baseline_since)
        if not ts_data:
            per_source[src] = {
                "zscore": 0.0, "cusum": 0.0,
                "velocity": 0.0, "acceleration": 0.0, "count_1d": 0,
            }
            continue

        # Build full daily count array aligned to calendar days
        day_map = {r["day"]: r["count"] for r in ts_data}
        all_days = [
            (baseline_since + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(max_days + 1)
        ]
        counts_all = np.array([float(day_map.get(d, 0)) for d in all_days])

        # --- Compute and persist snapshot for each window ---
        primary = {"zscore": 0.0, "cusum": 0.0, "velocity": 0.0, "acceleration": 0.0, "count_1d": 0}

        for window_days, baseline_days in WINDOW_BASELINES.items():
            # Build rolling-sum series for this window over the last (baseline_days + 1) points
            roll = _rolling_sums(counts_all, window_days)
            # Take the tail: baseline_days history + 1 current point
            series = roll[-(baseline_days + 1):]

            w_count = int(series[-1])
            w_z = _zscore(series)
            w_cusum = _cusum(series, k=config.CUSUM_K, h=config.CUSUM_H)
            w_vel, w_acc = _derivative(series)

            store.upsert_velocity_snapshot({
                "theme_id": theme_id,
                "source": src,
                "window_days": window_days,
                "ts": now.isoformat(),
                "mention_count": w_count,
                "velocity": w_vel,
                "acceleration": w_acc,
                "zscore": w_z,
                "cusum": w_cusum,
            })

            if window_days == COMPOSITE_WINDOW:
                primary = {
                    "zscore": w_z,
                    "cusum": w_cusum,
                    "velocity": w_vel,
                    "acceleration": w_acc,
                    "count_1d": w_count,
                }

        per_source[src] = primary

        # Source-level breach uses the primary (1-day) window
        src_breaching = (
            primary["zscore"] >= config.VELOCITY_Z_THRESHOLD
            or primary["cusum"] >= config.CUSUM_H
        )
        if src_breaching:
            breaching_sources.add(src)

        w = SOURCE_WEIGHTS.get(src, 0.5)
        z_contrib = min(max(primary["zscore"], 0.0), 5.0) / 5.0
        source_scores.append(z_contrib * w)

        # Earliness tracking using 1-day counts
        count_1d = primary["count_1d"]
        if src in EARLY_SOURCES:
            early_mentions += count_1d
        if src in LATE_SOURCES:
            late_mentions += count_1d

    # Composite 0–100 (FR-VEL-6)
    if source_scores:
        raw = np.mean(source_scores)
        diversity_bonus = min(len(breaching_sources) / len(SOURCES), 1.0) * 0.3
        composite = min((raw + diversity_bonus) * 100, 100.0)
    else:
        composite = 0.0

    # Earliness: ratio of early-source mentions to total (FR-VEL-8)
    total_mentions = early_mentions + late_mentions
    earliness = (early_mentions / total_mentions) if total_mentions > 0 else 0.5

    # Composite breach gate (FR-VEL-7)
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
    """Run velocity computation for all (or specified) themes; fire alerts on breach."""
    from backend.alerts.dispatcher import maybe_fire

    themes = store.get_all_themes()
    target_ids = set(theme_ids) if theme_ids else {t["theme_id"] for t in themes}
    theme_names = {t["theme_id"]: t["name"] for t in themes}

    results: list[VelocityResult] = []
    now = datetime.now(timezone.utc)
    for t in themes:
        if t["theme_id"] not in target_ids:
            continue
        try:
            r = compute_theme_velocity(t["theme_id"], now=now)
            results.append(r)
            log.debug("velocity %s: score=%.1f breach=%s", t["theme_id"], r.composite_score, r.breaching)
            if r.breaching:
                maybe_fire(theme_names.get(t["theme_id"], t["theme_id"]), r)
        except Exception as exc:
            log.error("velocity error for %s: %s", t["theme_id"], exc)
    return results
