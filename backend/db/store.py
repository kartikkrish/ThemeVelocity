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
    _migrate(conn)
    conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    """Idempotent column additions for tables created before a schema change."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(theme_analysis)")}
    if "synth_model" not in cols:
        conn.execute("ALTER TABLE theme_analysis ADD COLUMN synth_model TEXT")


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


def insert_event_entity(event_id: str, entity: str, entity_type: str, ticker: str | None, exchange: str | None) -> None:
    conn = _conn()
    conn.execute(
        "INSERT OR IGNORE INTO event_entities(event_id,entity,entity_type,ticker,exchange) VALUES(?,?,?,?,?)",
        (event_id, entity, entity_type, ticker, exchange),
    )
    conn.commit()


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


def get_recent_theme_events(theme_id: str, since: datetime, limit: int = 30) -> list[dict]:
    rows = _conn().execute(
        """SELECT e.raw_text, e.source, e.published_at FROM event_themes et
           JOIN events e ON et.event_id = e.event_id
           WHERE et.theme_id=? AND e.published_at>=?
           ORDER BY e.published_at DESC LIMIT ?""",
        (theme_id, since.isoformat(), limit),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_theme_analysis(row: dict) -> None:
    conn = _conn()
    conn.execute(
        """INSERT INTO theme_analysis
           (theme_id,analyzed_at,one_line_thesis,is_real_theme,catalyst_type,catalyst_detail,
            maturity_stage,earliness,c_velocity,c_source,c_catalyst,c_earliness,
            c_linkage,c_liquidity,c_total,dominant_tag,synth_model)
           VALUES(:theme_id,:analyzed_at,:one_line_thesis,:is_real_theme,:catalyst_type,
                  :catalyst_detail,:maturity_stage,:earliness,:c_velocity,:c_source,
                  :c_catalyst,:c_earliness,:c_linkage,:c_liquidity,:c_total,:dominant_tag,:synth_model)
           ON CONFLICT(theme_id,analyzed_at) DO UPDATE SET
             one_line_thesis=excluded.one_line_thesis,
             is_real_theme=excluded.is_real_theme,
             catalyst_type=excluded.catalyst_type,
             catalyst_detail=excluded.catalyst_detail,
             maturity_stage=excluded.maturity_stage,
             c_velocity=excluded.c_velocity, c_source=excluded.c_source,
             c_catalyst=excluded.c_catalyst, c_earliness=excluded.c_earliness,
             c_linkage=excluded.c_linkage, c_liquidity=excluded.c_liquidity,
             c_total=excluded.c_total, dominant_tag=excluded.dominant_tag,
             synth_model=excluded.synth_model""",
        row,
    )
    conn.commit()


def get_theme_analysis(theme_id: str) -> dict | None:
    row = _conn().execute(
        "SELECT * FROM theme_analysis WHERE theme_id=? ORDER BY analyzed_at DESC LIMIT 1",
        (theme_id,),
    ).fetchone()
    return dict(row) if row else None


def replace_value_chain(theme_id: str, nodes: list[dict]) -> None:
    conn = _conn()
    conn.execute("DELETE FROM value_chain_nodes WHERE theme_id=?", (theme_id,))
    for n in nodes:
        conn.execute(
            """INSERT INTO value_chain_nodes
               (theme_id,node_role,ticker,exchange,company_name,linkage_tightness,
                justification,liquidity_flag,epistemic_tag)
               VALUES(:theme_id,:node_role,:ticker,:exchange,:company_name,
                      :linkage_tightness,:justification,:liquidity_flag,:epistemic_tag)""",
            n,
        )
    conn.commit()


def get_value_chain(theme_id: str) -> list[dict]:
    rows = _conn().execute(
        "SELECT * FROM value_chain_nodes WHERE theme_id=? ORDER BY id",
        (theme_id,),
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


def get_last_alert_score(theme_id: str) -> float | None:
    row = _conn().execute(
        "SELECT payload FROM alerts WHERE theme_id=? ORDER BY fired_at DESC LIMIT 1",
        (theme_id,),
    ).fetchone()
    if not row or not row["payload"]:
        return None
    data = json.loads(row["payload"])
    return data.get("composite_score")


def get_model_settings() -> dict:
    """Return persisted model settings as a flat dict. Missing keys return empty string."""
    rows = _conn().execute("SELECT key, value FROM model_settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_model_setting(key: str, value: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn = _conn()
    conn.execute(
        "INSERT INTO model_settings(key,value,updated_at) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value, now),
    )
    conn.commit()


def get_watchlist() -> list[dict]:
    rows = _conn().execute(
        """SELECT w.theme_id, w.pinned_at, t.name,
                  cv.composite_score, cv.source_diversity, cv.earliness, cv.breaching, cv.ts
           FROM watchlist w
           JOIN themes t ON t.theme_id = w.theme_id
           LEFT JOIN (
             SELECT theme_id, MAX(ts) as max_ts FROM composite_velocity GROUP BY theme_id
           ) latest ON latest.theme_id = w.theme_id
           LEFT JOIN composite_velocity cv ON cv.theme_id = w.theme_id AND cv.ts = latest.max_ts
           ORDER BY w.pinned_at DESC"""
    ).fetchall()
    return [dict(r) for r in rows]


def toggle_watchlist(theme_id: str) -> bool:
    """Add if not present, remove if present. Returns True if now pinned."""
    conn = _conn()
    existing = conn.execute("SELECT 1 FROM watchlist WHERE theme_id=?", (theme_id,)).fetchone()
    if existing:
        conn.execute("DELETE FROM watchlist WHERE theme_id=?", (theme_id,))
        conn.commit()
        return False
    else:
        from datetime import datetime, timezone
        conn.execute("INSERT INTO watchlist(theme_id, pinned_at) VALUES(?,?)",
                     (theme_id, datetime.now(timezone.utc).isoformat()))
        conn.commit()
        return True


def replace_india_crossmap(theme_id: str, nodes: list[dict]) -> None:
    conn = _conn()
    conn.execute("DELETE FROM india_crossmap WHERE theme_id=?", (theme_id,))
    for n in nodes:
        conn.execute(
            """INSERT INTO india_crossmap
               (theme_id,node_role,ticker,exchange,company_name,linkage_tightness,
                justification,liquidity_flag,epistemic_tag)
               VALUES(:theme_id,:node_role,:ticker,:exchange,:company_name,
                      :linkage_tightness,:justification,:liquidity_flag,:epistemic_tag)""",
            n,
        )
    conn.commit()


def get_india_crossmap(theme_id: str) -> list[dict]:
    rows = _conn().execute(
        "SELECT * FROM india_crossmap WHERE theme_id=? ORDER BY id",
        (theme_id,),
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
