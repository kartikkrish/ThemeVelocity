#!/usr/bin/env python3
"""Seed synthetic velocity data for P1 dashboard validation.

Simulates ~90 days of mention history for each theme×source,
with a realistic acceleration spike in the final 7–14 days for
the "hot" themes. Run once after init to make the dashboard usable.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from datetime import datetime, timedelta, timezone

from backend.db.store import init_db
from backend.engine.themes import tagger
from backend.engine.velocity import run_velocity_cycle
from backend.db import store

SOURCES = [
    ("edgar", 1.0),
    ("hn", 0.7),
    ("gdelt", 0.6),
]

# How hot each theme is in the mock data (0 = flat, 1 = strong acceleration)
THEME_HEAT = {
    "liquid_cooling":    0.90,
    "cpo":               0.75,
    "agentic_ai":        0.85,
    "ai_inference":      0.80,
    "nuclear_power":     0.60,
    "grid_transformers": 0.55,
    "humanoid_robotics": 0.45,
    "power_electronics": 0.35,
}

np.random.seed(42)


def generate_counts(heat: float, days: int = 90) -> list[int]:
    """Simulate daily mention counts with acceleration in final 14 days."""
    baseline = np.random.poisson(lam=max(2, heat * 5), size=days - 14).astype(float)
    # spike: exponential ramp in last 14 days
    ramp = np.exp(np.linspace(0, heat * 2.5, 14)) * max(1, heat * 3)
    spike = np.random.poisson(lam=ramp).astype(float)
    counts = np.concatenate([baseline, spike])
    return [max(0, int(c)) for c in counts]


def insert_synthetic_events(theme_id: str, source: str, weight: float, counts: list[int]):
    """Insert fake events so the timeseries query works."""
    now = datetime.now(timezone.utc)
    for day_offset, count in enumerate(counts):
        pub_date = now - timedelta(days=len(counts) - day_offset - 1)
        for n in range(count):
            ev_id = f"mock_{theme_id}_{source}_{day_offset}_{n}"
            row = {
                "event_id": ev_id,
                "source": source,
                "source_weight": weight,
                "published_at": pub_date.isoformat(),
                "fetched_at": pub_date.isoformat(),
                "raw_text": f"[mock] {theme_id} mention",
                "url": f"https://example.com/{theme_id}/{day_offset}/{n}",
                "syndication_count": 1,
            }
            store.upsert_event(row)
            store.insert_event_theme(ev_id, theme_id, 0.8)


def main():
    init_db()
    tagger.load()
    themes = store.get_all_themes()

    print(f"Seeding {len(themes)} themes × {len(SOURCES)} sources × 90 days …")
    for t in themes:
        tid = t["theme_id"]
        heat = THEME_HEAT.get(tid, 0.3)
        for src, w in SOURCES:
            counts = generate_counts(heat)
            insert_synthetic_events(tid, src, w, counts)
            total = sum(counts)
            print(f"  {tid:<22} {src:<8} total={total:4d}  heat={heat:.2f}")

    print("\nRunning velocity cycle …")
    results = run_velocity_cycle()
    results.sort(key=lambda r: r.composite_score, reverse=True)
    print("\nTheme Velocity Rankings:")
    print(f"{'Theme':<25} {'Score':>6}  {'Div':>4}  {'Early':>6}  {'Breach':>7}")
    print("-" * 56)
    for r in results:
        print(f"{r.theme_id:<25} {r.composite_score:>6.1f}  {r.source_diversity:>4}  {r.earliness:>6.2f}  {'✓' if r.breaching else '':>7}")

    print("\nDone. Dashboard should now show live data.")


if __name__ == "__main__":
    main()
