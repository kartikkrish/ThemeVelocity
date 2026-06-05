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
    BeneficiaryNode,
    ConfidenceData,
    IngestionStatus,
    SourceSnapshot,
    SynthesisData,
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


def _edgar_job():
    now = datetime.now(timezone.utc)
    since = _last_ingestion.get("edgar", now - timedelta(days=7))
    log.info("edgar ingestion since=%s", since.isoformat())
    counts = run_ingestion(since=since, sources=["edgar"])
    _last_ingestion["edgar"] = now
    run_velocity_cycle()
    log.info("edgar ingestion complete: %s", counts)


def _hn_gdelt_job():
    now = datetime.now(timezone.utc)
    since = min(
        _last_ingestion.get(src, now - timedelta(days=7))
        for src in ["hn", "gdelt"]
    )
    log.info("hn/gdelt ingestion since=%s", since.isoformat())
    counts = run_ingestion(since=since, sources=["hn", "gdelt"])
    for src in ["hn", "gdelt"]:
        _last_ingestion[src] = now
    run_velocity_cycle()
    log.info("hn/gdelt ingestion complete: %s", counts)


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    tagger.load()
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(_edgar_job, "interval", seconds=config.EDGAR_POLL_SEC, id="ingest_edgar")
    scheduler.add_job(_hn_gdelt_job, "interval", seconds=config.HN_POLL_SEC, id="ingest_hn_gdelt")
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


def _enrich_heat(r: dict) -> ThemeHeat:
    analysis = store.get_theme_analysis(r["theme_id"])
    return ThemeHeat(
        theme_id=r["theme_id"],
        name=r["name"],
        composite_score=r["composite_score"],
        source_diversity=r["source_diversity"],
        earliness=r["earliness"],
        breaching=bool(r["breaching"]),
        ts=r["ts"],
        one_line_thesis=analysis["one_line_thesis"] if analysis else None,
        catalyst_type=analysis["catalyst_type"] if analysis else None,
        maturity_stage=analysis["maturity_stage"] if analysis else None,
    )


@app.get("/api/themes/heat", response_model=list[ThemeHeat])
def get_theme_heat(limit: int = 20):
    return [_enrich_heat(r) for r in store.get_trending_themes(limit=limit)]


@app.get("/api/themes/trending", response_model=list[ThemeHeat])
def get_trending(tab: str = "daily", limit: int = 20):
    return [_enrich_heat(r) for r in store.get_trending_themes(limit=limit)]


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

    # Phase 2: synthesis + confidence
    analysis = store.get_theme_analysis(t["theme_id"])
    synthesis_out = None
    confidence_out = None
    if analysis:
        synthesis_out = SynthesisData(
            one_line_thesis=analysis["one_line_thesis"] or "",
            catalyst_type=analysis["catalyst_type"] or "",
            catalyst_detail=analysis["catalyst_detail"] or "",
            maturity_stage=analysis["maturity_stage"] or "",
            is_real_theme=bool(analysis["is_real_theme"]),
            key_entities=[],
            epistemic_tag=analysis["dominant_tag"] or "I",
        )
        confidence_out = ConfidenceData(
            c_velocity=analysis["c_velocity"] or 0,
            c_source=analysis["c_source"] or 0,
            c_catalyst=analysis["c_catalyst"] or 0,
            c_earliness=analysis["c_earliness"] or 0,
            c_linkage=analysis["c_linkage"] or 0,
            c_liquidity=analysis["c_liquidity"] or 0,
            c_total=analysis["c_total"] or 0,
            epistemic_tag=analysis["dominant_tag"] or "I",
        )

    # Phase 3: value chain
    vc_rows = store.get_value_chain(t["theme_id"])
    beneficiaries = [
        BeneficiaryNode(
            node_role=n["node_role"],
            company_name=n["company_name"],
            ticker=n["ticker"] or "",
            exchange=n["exchange"] or "",
            linkage_tightness=n["linkage_tightness"],
            justification=n["justification"] or "",
            epistemic_tag=n["epistemic_tag"] or "I",
        )
        for n in vc_rows
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
        synthesis=synthesis_out,
        confidence=confidence_out,
        beneficiaries=beneficiaries,
    )


@app.get("/api/alerts", response_model=list[AlertItem])
def get_alerts(limit: int = 50):
    rows = store.get_recent_alerts(limit=limit)
    results = []
    for r in rows:
        payload = json.loads(r["payload"]) if r["payload"] else {}
        analysis = store.get_theme_analysis(r["theme_id"])
        results.append(AlertItem(
            alert_id=r["alert_id"],
            theme_id=r["theme_id"],
            theme_name=payload.get("theme_name", r["theme_id"]),
            fired_at=r["fired_at"],
            composite_score=payload.get("composite_score", 0),
            one_line_thesis=analysis["one_line_thesis"] if analysis else None,
            acknowledged=bool(r["acknowledged"]),
        ))
    return results


@app.post("/api/themes/{theme_id}/analyze")
def analyze_theme(theme_id: str, background_tasks: BackgroundTasks):
    """Trigger LLM synthesis + value-chain for a specific theme."""
    def _run():
        from backend.engine.synthesis import synthesize_and_store
        from backend.engine.value_chain import run_value_chain
        comp = store.get_latest_composite(theme_id)
        if not comp:
            return
        from backend.engine.velocity import VelocityResult
        result = VelocityResult(
            theme_id=theme_id,
            composite_score=comp["composite_score"],
            source_diversity=comp["source_diversity"],
            earliness=comp["earliness"],
            breaching=bool(comp["breaching"]),
            per_source={},
        )
        synthesize_and_store(theme_id, result)
        run_value_chain(theme_id)

    background_tasks.add_task(_run)
    return {"status": "analysis triggered", "theme_id": theme_id}


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
