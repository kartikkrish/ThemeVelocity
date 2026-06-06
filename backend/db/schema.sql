CREATE TABLE IF NOT EXISTS events (
  event_id          TEXT PRIMARY KEY,
  source            TEXT NOT NULL,
  source_weight     REAL NOT NULL,
  published_at      TIMESTAMP NOT NULL,
  fetched_at        TIMESTAMP NOT NULL,
  raw_text          TEXT,
  url               TEXT,
  syndication_count INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS event_entities (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id    TEXT REFERENCES events(event_id),
  entity      TEXT,
  entity_type TEXT,
  ticker      TEXT,
  exchange    TEXT
);

CREATE TABLE IF NOT EXISTS event_themes (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id   TEXT REFERENCES events(event_id),
  theme_id   TEXT REFERENCES themes(theme_id),
  confidence REAL
);

CREATE TABLE IF NOT EXISTS themes (
  theme_id   TEXT PRIMARY KEY,
  name       TEXT NOT NULL,
  primitive  TEXT,
  keywords   TEXT NOT NULL,   -- JSON array
  status     TEXT DEFAULT 'candidate',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS velocity_snapshots (
  theme_id      TEXT REFERENCES themes(theme_id),
  source        TEXT NOT NULL,
  window_days   INTEGER NOT NULL,
  ts            TIMESTAMP NOT NULL,
  mention_count INTEGER DEFAULT 0,
  velocity      REAL DEFAULT 0,
  acceleration  REAL DEFAULT 0,
  zscore        REAL DEFAULT 0,
  cusum         REAL DEFAULT 0,
  PRIMARY KEY (theme_id, source, window_days, ts)
);

CREATE TABLE IF NOT EXISTS composite_velocity (
  theme_id          TEXT REFERENCES themes(theme_id),
  ts                TIMESTAMP NOT NULL,
  composite_score   REAL DEFAULT 0,
  source_diversity  INTEGER DEFAULT 0,
  earliness         REAL DEFAULT 0,
  breaching         INTEGER DEFAULT 0,
  PRIMARY KEY (theme_id, ts)
);

CREATE TABLE IF NOT EXISTS theme_analysis (
  theme_id        TEXT REFERENCES themes(theme_id),
  analyzed_at     TIMESTAMP NOT NULL,
  one_line_thesis TEXT,
  is_real_theme   INTEGER,
  catalyst_type   TEXT,
  catalyst_detail TEXT,
  maturity_stage  TEXT,
  earliness       REAL,
  c_velocity      REAL,
  c_source        REAL,
  c_catalyst      REAL,
  c_earliness     REAL,
  c_linkage       REAL,
  c_liquidity     REAL,
  c_total         REAL,
  dominant_tag    TEXT,
  synth_model     TEXT,         -- model that produced this synthesis (for confidence flagging)
  PRIMARY KEY (theme_id, analyzed_at)
);

CREATE TABLE IF NOT EXISTS value_chain_nodes (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  theme_id          TEXT REFERENCES themes(theme_id),
  node_role         TEXT,
  ticker            TEXT,
  exchange          TEXT,
  company_name      TEXT,
  linkage_tightness TEXT,
  justification     TEXT,
  liquidity_flag    TEXT,
  epistemic_tag     TEXT
);

CREATE TABLE IF NOT EXISTS alerts (
  alert_id     TEXT PRIMARY KEY,
  theme_id     TEXT REFERENCES themes(theme_id),
  fired_at     TIMESTAMP,
  payload      TEXT,
  acknowledged INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS model_settings (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watchlist (
  theme_id   TEXT PRIMARY KEY REFERENCES themes(theme_id),
  pinned_at  TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS india_crossmap (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  theme_id          TEXT REFERENCES themes(theme_id),
  node_role         TEXT,
  ticker            TEXT,
  exchange          TEXT,
  company_name      TEXT,
  linkage_tightness TEXT,
  justification     TEXT,
  liquidity_flag    TEXT,
  epistemic_tag     TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_source_published ON events(source, published_at);
CREATE INDEX IF NOT EXISTS idx_event_themes_theme ON event_themes(theme_id);
CREATE INDEX IF NOT EXISTS idx_velocity_theme_ts ON velocity_snapshots(theme_id, ts);
CREATE INDEX IF NOT EXISTS idx_composite_theme_ts ON composite_velocity(theme_id, ts);
