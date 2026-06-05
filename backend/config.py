import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = os.getenv("TV_DB_PATH", str(DATA_DIR / "themevelocity.db"))

# Velocity thresholds
VELOCITY_Z_THRESHOLD = float(os.getenv("TV_Z_THRESHOLD", "2.0"))
CUSUM_H = float(os.getenv("TV_CUSUM_H", "4.0"))          # CUSUM decision interval
CUSUM_K = float(os.getenv("TV_CUSUM_K", "0.5"))          # CUSUM allowance
DIVERSITY_MIN_SOURCES = int(os.getenv("TV_DIVERSITY_MIN", "2"))  # min source types for composite breach

# Polling cadences (seconds)
EDGAR_POLL_SEC = int(os.getenv("TV_EDGAR_POLL", "3600"))   # 1 hour
HN_POLL_SEC    = int(os.getenv("TV_HN_POLL",    "900"))    # 15 min
GDELT_POLL_SEC = int(os.getenv("TV_GDELT_POLL",  "900"))   # 15 min

# FastAPI
API_HOST = os.getenv("TV_API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("TV_API_PORT", "8765"))

# Rolling windows (days)
WINDOWS = [1, 7, 30, 90]
BASELINE_DAYS = 60   # Z-score baseline
