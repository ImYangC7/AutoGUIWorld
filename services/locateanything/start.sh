#!/bin/bash
# Start or stop the local grounding service identified by its own PID file.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${LA_PORT:-8004}"
GPU="${LA_GPU:-0}"
REPLICAS="${LA_REPLICAS:-1}"
RUNTIME="$HERE/.runtime"
PY="$HERE/.venv/bin/python"
case "$PORT" in ''|*[!0-9]*) echo "LA_PORT must be an integer" >&2; exit 2;; esac
case "$REPLICAS" in ''|*[!0-9]*) echo "LA_REPLICAS must be an integer" >&2; exit 2;; esac
if (( 10#$PORT < 1 || 10#$PORT > 65535 || 10#$REPLICAS < 1 )); then
  echo "Invalid port or replica count" >&2
  exit 2
fi
PID_FILE="$RUNTIME/$PORT.pid"
LOG="$RUNTIME/$PORT.log"
ACTION="${1:-start}"
if [[ "$ACTION" != start && "$ACTION" != stop ]]; then
  echo "Usage: bash start.sh [start|stop]" >&2
  exit 2
fi
if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  case "$PID" in ''|*[!0-9]*) echo "Invalid service PID file" >&2; exit 1;; esac
  if kill -0 "$PID" 2>/dev/null; then
    PROCESS="$(ps -p "$PID" -o args=)"
    if [[ "$PROCESS" != *"$PY -m uvicorn server:app"* || "$PROCESS" != *"--port $PORT" ]]; then
      echo "PID does not identify this service; refusing to signal it" >&2
      exit 1
    fi
    if [[ "$ACTION" == stop ]]; then
      kill "$PID"
      rm -f "$PID_FILE"
      echo "Stop requested for service PID $PID"
      exit 0
    fi
    echo "Service already running as PID $PID"
    exit 0
  fi
  rm -f "$PID_FILE"
fi
if [[ "$ACTION" == stop ]]; then
  echo "No managed service running on port $PORT"
  exit 0
fi
if [[ ! -x "$PY" ]]; then
  echo "Create services/locateanything/.venv and install the service dependencies first" >&2
  exit 2
fi
if [[ -z "${LA_MODEL_PATH:-}" || ! -d "$LA_MODEL_PATH" ]]; then
  echo "LA_MODEL_PATH must point to the installed model directory" >&2
  exit 2
fi
mkdir -p "$RUNTIME"
cd "$HERE"
CUDA_VISIBLE_DEVICES="$GPU" LA_REPLICAS="$REPLICAS" \
  PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True" \
  nohup "$PY" -m uvicorn server:app \
  --host "${LA_HOST:-127.0.0.1}" --port "$PORT" > "$LOG" 2>&1 &
PID=$!
printf '%s\n' "$PID" > "$PID_FILE"
sleep 1
if ! kill -0 "$PID" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "Service exited during startup; inspect $LOG" >&2
  exit 1
fi
echo "Started PID $PID; log: $LOG"
echo "Model loading continues; check readiness at localhost:$PORT/health"
