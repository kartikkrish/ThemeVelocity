"""FastAPI application — Phase 1 read layer."""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from backend import config
from backend.api.schemas import (
    AlertItem,
    IngestionStatus,
    SourceSnapshot,
    ThemeDetail,
    ThemeHeat,
    VelocityPoint,
)
from backend.db import store
from backend.engine.themes import tagger
from backend.engine.velocity import run_velocity_cycle
from backend.ingestion.pipeline import run_ingestion

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scheduler state
# ---------------------------------------------------------------------------
_last_ingestion: dict[str, datetime] = {}


def _ingestion_job():
    src_windows = {
        "edgar": timedelta(seconds=config.EDGAR_POLL_SEC),
        "hn": timedelta(seconds=config.HN_POLL_SEC),
        "gdelt": timedelta(seconds=config.GDELT_POLL_SEC),
    }
    now = datetime.now(timezone.utc)
    since = min(
        _last_ingestion.get(src, now - timedelta(days=7))
        for src in ["edgar", "hn", "gdelt"]
    )
    log.info("scheduled ingestion since=%s", since.isoformat())
    counts = run_ingestion(since=since)
    for src in src_windows:
        _last_ingestion[src] = now
    run_velocity_cycle()
    log.info("scheduled ingestion complete: %s", counts)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    tagger.load()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(_ingestion_job, "interval", seconds=config.HN_POLL_SEC, id="ingest")
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="ThemeVelocity API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/themes/heat", response_model=list[ThemeHeat])
def get_theme_heat(limit: int = 20):
    rows = store.get_trending_themes(limit=limit)
    return [
        ThemeHeat(
            theme_id=r["theme_id"],
            name=r["name"],
            composite_score=r["composite_score"],
            source_diversity=r["source_diversity"],
            earliness=r["earliness"],
            breaching=bool(r["breaching"]),
            ts=r["ts"],
        )
        for r in rows
    ]


@app.get("/api/themes/trending", response_model=list[ThemeHeat])
def get_trending(tab: str = "daily", limit: int = 20):
    rows = store.get_trending_themes(limit=limit)
    return [
        ThemeHeat(
            theme_id=r["theme_id"],
            name=r["name"],
            composite_score=r["composite_score"],
            source_diversity=r["source_diversity"],
            earliness=r["earliness"],
            breaching=bool(r["breaching"]),
            ts=r["ts"],
        )
        for r in rows
    ]


@app.get("/api/themes/{theme_id}", response_model=ThemeDetail)
def get_theme(theme_id: str):
    t = store.get_theme(theme_id)
    if not t:
        raise HTTPException(status_code=404, detail="Theme not found")
    comp = store.get_latest_composite(theme_id)
    history_rows = store.get_composite_history(theme_id, limit=90)

    per_source: list[SourceSnapshot] = []
    from backend.engine.velocity import SOURCES
    for src in SOURCES:
        snaps = store.get_velocity_history(theme_id, src, window_days=1, limit=1)
        if snaps:
            s = snaps[-1]
            per_source.append(SourceSnapshot(
                source=src,
                zscore=s["zscore"],
                cusum=s["cusum"],
                velocity=s["velocity"],
                acceleration=s["acceleration"],
                count_1d=s["mention_count"],
            ))
        else:
            per_source.append(SourceSnapshot(source=src, zscore=0, cusum=0, velocity=0, acceleration=0, count_1d=0))

    velocity_history = [
        VelocityPoint(
            ts=h["ts"],
            composite_score=h["composite_score"],
            source_diversity=h["source_diversity"],
            earliness=h["earliness"],
            breaching=bool(h["breaching"]),
        )
        for h in history_rows
    ]

    return ThemeDetail(
        theme_id=t["theme_id"],
        name=t["name"],
        primitive=t.get("primitive"),
        status=t["status"],
        composite_score=comp["composite_score"] if comp else 0.0,
        source_diversity=comp["source_diversity"] if comp else 0,
        earliness=comp["earliness"] if comp else 0.0,
        breaching=bool(comp["breaching"]) if comp else False,
        per_source=per_source,
        velocity_history=velocity_history,
    )


@app.get("/api/alerts", response_model=list[AlertItem])
def get_alerts(limit: int = 50):
    rows = store.get_recent_alerts(limit=limit)
    return [
        AlertItem(
            alert_id=r["alert_id"],
            theme_id=r["theme_id"],
            fired_at=r["fired_at"],
            composite_score=json.loads(r["payload"]).get("composite_score", 0) if r["payload"] else 0,
            acknowledged=bool(r["acknowledged"]),
        )
        for r in rows
    ]


@app.post("/api/ingest/trigger", response_model=IngestionStatus)
def trigger_ingestion(background_tasks: BackgroundTasks):
    """Manual trigger for testing/backfill."""
    def _run():
        since = datetime.now(timezone.utc) - timedelta(days=7)
        counts = run_ingestion(since=since)
        run_velocity_cycle()
        log.info("manual ingestion: %s", counts)

    background_tasks.add_task(_run)
    return IngestionStatus(status="triggered", counts={})


@app.post("/api/velocity/run")
def run_velocity():
    """Manual velocity recompute."""
    results = run_velocity_cycle()
    return {
        "computed": len(results),
        "breaching": [r.theme_id for r in results if r.breaching],
    }
