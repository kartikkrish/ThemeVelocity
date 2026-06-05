"""Alert dispatcher — fires on velocity breach, throttles re-alerts.

FR-ALERT-1: Telegram bot primary, silent fallback if not configured.
FR-ALERT-2: Payload includes theme name, composite score, per-source
            Z-scores, earliness, and a link to the dashboard detail.
FR-ALERT-3: No auto-trade — this module only sends notifications.
FR-ALERT-4: Throttled by cooldown window + refire delta on score jump.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone

import requests

from backend import config
from backend.db import store
from backend.engine.velocity import VelocityResult

log = logging.getLogger(__name__)

_TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"


def _telegram_send(message: str) -> bool:
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False
    try:
        resp = requests.post(
            _TELEGRAM_URL.format(token=config.TELEGRAM_TOKEN),
            json={
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        log.warning("Telegram dispatch failed: %s", exc)
        return False


def _build_message(theme_name: str, result: VelocityResult) -> str:
    src_lines = "\n".join(
        f"  • {src}: Z={v['zscore']:.1f}  CUSUM={v['cusum']:.1f}"
        for src, v in result.per_source.items()
        if v.get("zscore", 0) > 0 or v.get("cusum", 0) > 0
    )
    dashboard = f"{config.DASHBOARD_URL}/theme/{result.theme_id}"
    return (
        f"*ThemeVelocity Alert* 🚀\n"
        f"*{theme_name}*\n\n"
        f"Composite score: *{result.composite_score:.0f}/100*\n"
        f"Sources breaching: {result.source_diversity}\n"
        f"Earliness: {result.earliness:.0%}\n\n"
        f"Per-source signals:\n{src_lines}\n\n"
        f"[View on dashboard]({dashboard})"
    )


def _should_fire(theme_id: str, composite_score: float) -> bool:
    if not store.was_alerted_recently(theme_id, hours=config.ALERT_COOLDOWN_HOURS):
        return True
    last_score = store.get_last_alert_score(theme_id)
    return last_score is not None and composite_score >= last_score + config.ALERT_REFIRE_DELTA


def maybe_fire(theme_name: str, result: VelocityResult) -> bool:
    """Fire an alert if the theme is breaching and not throttled. Returns True if fired."""
    if not result.breaching:
        return False
    if not _should_fire(result.theme_id, result.composite_score):
        log.debug("alert throttled for %s (score=%.1f)", result.theme_id, result.composite_score)
        return False

    now = datetime.now(timezone.utc)
    payload = {
        "theme_id": result.theme_id,
        "theme_name": theme_name,
        "composite_score": result.composite_score,
        "source_diversity": result.source_diversity,
        "earliness": result.earliness,
        "per_source": result.per_source,
        "dashboard_url": f"{config.DASHBOARD_URL}/theme/{result.theme_id}",
    }
    alert_id = hashlib.sha1(
        f"{result.theme_id}|{now.isoformat()}".encode()
    ).hexdigest()[:20]

    store.insert_alert({
        "alert_id": alert_id,
        "theme_id": result.theme_id,
        "fired_at": now.isoformat(),
        "payload": json.dumps(payload),
        "acknowledged": 0,
    })

    message = _build_message(theme_name, result)
    sent = _telegram_send(message)
    log.info(
        "alert fired: theme=%s score=%.1f telegram=%s",
        result.theme_id, result.composite_score, sent,
    )
    return True
