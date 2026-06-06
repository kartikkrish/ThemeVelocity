#!/usr/bin/env bash
# ThemeVelocity — start backend + frontend together.
# Usage:  ./run.sh        (start both, Ctrl-C stops both)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT=8765
FRONTEND_PORT=5173

# --- preflight ------------------------------------------------------------
[ -x .venv/bin/python ] || { echo "✗ .venv missing — run: python3.12 -m venv .venv && .venv/bin/pip install -e ."; exit 1; }
[ -d frontend/node_modules ] || { echo "✗ frontend deps missing — run: cd frontend && npm install"; exit 1; }

# Free stale ports
for p in $BACKEND_PORT $FRONTEND_PORT; do
  pid=$(lsof -ti:"$p" 2>/dev/null || true)
  [ -n "$pid" ] && { echo "• freeing port $p (pid $pid)"; kill "$pid" 2>/dev/null || true; }
done

# Optional: start Ollama if installed and not already up (agentic layer)
if command -v ollama >/dev/null 2>&1 && ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "• starting ollama daemon"
  ollama serve >/tmp/tv_ollama.log 2>&1 &
fi

# --- cleanup on exit ------------------------------------------------------
PIDS=()
cleanup() {
  echo; echo "• stopping…"
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  exit 0
}
trap cleanup INT TERM

# --- backend --------------------------------------------------------------
echo "→ backend  http://localhost:$BACKEND_PORT"
.venv/bin/python run_backend.py > /tmp/tv_backend.log 2>&1 &
PIDS+=($!)

# wait for health before starting frontend
for _ in $(seq 1 20); do
  curl -sf http://localhost:$BACKEND_PORT/health >/dev/null 2>&1 && break
  sleep 1
done
curl -sf http://localhost:$BACKEND_PORT/health >/dev/null 2>&1 \
  && echo "  ✓ backend up" \
  || { echo "  ✗ backend failed — see /tmp/tv_backend.log"; tail -15 /tmp/tv_backend.log; cleanup; }

# --- frontend -------------------------------------------------------------
echo "→ frontend http://localhost:$FRONTEND_PORT"
( cd frontend && npm run dev > /tmp/tv_frontend.log 2>&1 ) &
PIDS+=($!)

echo
echo "ThemeVelocity running. Open http://localhost:$FRONTEND_PORT"
echo "Logs: /tmp/tv_backend.log  /tmp/tv_frontend.log"
echo "Ctrl-C to stop both."
wait
