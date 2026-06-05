"""SQLite store — thin wrapper with connection pooling via thread-local."""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.config import DB_PATH

_local = threading.local()
_SCHEMA = Path(__file__).parent / "schema.sql"


def _conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        con = sqlite3.connect(DB_PATH, check_same_thread=False)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        _local.conn = con
    return _local.conn


def init_db() -> None:
    schema = _SCHEMA.read_text()
    conn = _conn()
    conn.executescript(schema)
    conn.commit()


def upsert_event(row: dict) -> bool:
    """Returns True if inserted (new), False if already existed."""
    conn = _conn()
    try:
        conn.execute(
            """INSERT INTO events
               (event_id, source, source_weight, published_at, fetched_at, raw_text, url, syndication_count)
               VALUES (:event_id,:source,:source_weight,:published_at,:fetched_at,:raw_text,:url,:syndication_count)
               ON CONFLICT(event_id) DO UPDATE SET syndication_count = syndication_count + 1""",
            row,
        )
        conn.commit()
        return conn.execute("SELECT changes()").fetchone()[0] > 0
    except Exception:
        conn.rollback()
        raise


def insert_event_theme(event_id: str, theme_id: str, confidence: float) -> None:
    conn = _conn()
    conn.execute(
        "INSERT OR IGNORE INTO event_themes(event_id,theme_id,confidence) VALUES(?,?,?)",
        (event_id, theme_id, confidence),
    )
    conn.commit()


def upsert_theme(theme: dict) -> None:
    conn = _conn()
    conn.execute(
        """INSERT INTO themes(theme_id,name,primitive,keywords,status,created_at)
           VALUES(:theme_id,:name,:primitive,:keywords,:status,:created_at)
           ON CONFLICT(theme_id) DO NOTHING""",
        theme,
    )
    conn.commit()


def get_all_themes() -> list[dict]:
    rows = _conn().execute("SELECT * FROM themes WHERE status != 'archived'").fetchall()
    return [dict(r) for r in rows]


def get_theme(theme_id: str) -> dict | None:
    row = _conn().execute("SELECT * FROM themes WHERE theme_id=?", (theme_id,)).fetchone()
    return dict(row) if row else None


def count_mentions(theme_id: str, source: str, since: datetime) -> int:
    conn = _conn()
    row = conn.execute(
        """SELECT COUNT(*) FROM event_themes et
           JOIN events e ON et.event_id = e.event_id
           WHERE et.theme_id=? AND e.source=? AND e.published_at>=?""",
        (theme_id, source, since.isoformat()),
    ).fetchone()
    return row[0] if row else 0


def get_mention_timeseries(theme_id: str, source: str, since: datetime) -> list[dict]:
    """Daily mention counts per theme×source since a date."""
    rows = _conn().execute(
        """SELECT date(e.published_at) as day, COUNT(*) as cnt
           FROM event_themes et JOIN events e ON et.event_id=e.event_id
           WHERE et.theme_id=? AND e.source=? AND e.published_at>=?
           GROUP BY day ORDER BY day""",
        (theme_id, source, since.isoformat()),
    ).fetchall()
    return [{"day": r["day"], "count": r["cnt"]} for r in rows]


def upsert_velocity_snapshot(row: dict) -> None:
    conn = _conn()
    conn.execute(
        """INSERT INTO velocity_snapshots
           (theme_id,source,window_days,ts,mention_count,velocity,acceleration,zscore,cusum)
           VALUES(:theme_id,:source,:window_days,:ts,:mention_count,:velocity,:acceleration,:zscore,:cusum)
           ON CONFLICT(theme_id,source,window_days,ts) DO UPDATE SET
             mention_count=excluded.mention_count, velocity=excluded.velocity,
             acceleration=excluded.acceleration, zscore=excluded.zscore, cusum=excluded.cusum""",
        row,
    )
    conn.commit()


def upsert_composite(row: dict) -> None:
    conn = _conn()
    conn.execute(
        """INSERT INTO composite_velocity(theme_id,ts,composite_score,source_diversity,earliness,breaching)
           VALUES(:theme_id,:ts,:composite_score,:source_diversity,:earliness,:breaching)
           ON CONFLICT(theme_id,ts) DO UPDATE SET
             composite_score=excluded.composite_score, source_diversity=excluded.source_diversity,
             earliness=excluded.earliness, breaching=excluded.breaching""",
        row,
    )
    conn.commit()


def get_latest_composite(theme_id: str) -> dict | None:
    row = _conn().execute(
        "SELECT * FROM composite_velocity WHERE theme_id=? ORDER BY ts DESC LIMIT 1",
        (theme_id,),
    ).fetchone()
    return dict(row) if row else None


def get_velocity_history(theme_id: str, source: str, window_days: int, limit: int = 90) -> list[dict]:
    rows = _conn().execute(
        """SELECT * FROM velocity_snapshots
           WHERE theme_id=? AND source=? AND window_days=?
           ORDER BY ts DESC LIMIT ?""",
        (theme_id, source, window_days, limit),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_composite_history(theme_id: str, limit: int = 90) -> list[dict]:
    rows = _conn().execute(
        "SELECT * FROM composite_velocity WHERE theme_id=? ORDER BY ts DESC LIMIT ?",
        (theme_id, limit),
    ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_trending_themes(limit: int = 20) -> list[dict]:
    """Latest composite score per theme, ordered by score desc."""
    rows = _conn().execute(
        """SELECT t.theme_id, t.name, t.primitive, t.status,
                  cv.composite_score, cv.source_diversity, cv.earliness, cv.breaching, cv.ts
           FROM themes t
           JOIN (
             SELECT theme_id, MAX(ts) as max_ts FROM composite_velocity GROUP BY theme_id
           ) latest ON t.theme_id=latest.theme_id
           JOIN composite_velocity cv ON cv.theme_id=t.theme_id AND cv.ts=latest.max_ts
           WHERE t.status != 'archived'
           ORDER BY cv.composite_score DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def insert_alert(row: dict) -> None:
    conn = _conn()
    conn.execute(
        """INSERT OR IGNORE INTO alerts(alert_id,theme_id,fired_at,payload,acknowledged)
           VALUES(:alert_id,:theme_id,:fired_at,:payload,:acknowledged)""",
        row,
    )
    conn.commit()


def get_recent_alerts(limit: int = 50) -> list[dict]:
    rows = _conn().execute(
        "SELECT * FROM alerts ORDER BY fired_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def was_alerted_recently(theme_id: str, hours: int = 24) -> bool:
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    row = _conn().execute(
        "SELECT 1 FROM alerts WHERE theme_id=? AND fired_at>=? LIMIT 1",
        (theme_id, cutoff),
    ).fetchone()
    return row is not None
