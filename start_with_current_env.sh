#!/usr/bin/env bash
# Start BioLab with CURRENT active environment and a fresh log file.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${BIOLAB_PROJECT_DIR:-$SCRIPT_DIR}"
LOG_FILE="${BIOLAB_LOG_FILE:-/tmp/biolab_current.log}"

cd "$PROJECT_DIR"

pick_python() {
  if command -v python >/dev/null 2>&1; then
    echo "python"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return 0
  fi
  return 1
}

PY_CMD="$(pick_python || true)"
if [ -z "$PY_CMD" ]; then
  echo "No python/python3 found in current shell. Activate environment first."
  exit 1
fi

if ! "$PY_CMD" -c "import flask" >/dev/null 2>&1; then
  echo "Current environment does not have flask."
  echo "Tip: conda activate <your_env>; then retry."
  exit 1
fi

echo "Using Python: $("$PY_CMD" -c 'import sys; print(sys.executable)')"
echo "Flask Version: $("$PY_CMD" -c 'from importlib.metadata import version; print(version(\"flask\"))')"

pkill -f "python.*run.py" || true
sleep 1

: > "$LOG_FILE"
nohup "$PY_CMD" run.py >> "$LOG_FILE" 2>&1 &
sleep 2

if pgrep -f "python.*run.py" >/dev/null 2>&1; then
  echo "Started. Log file: $LOG_FILE"
  echo "Use: tail -f $LOG_FILE"
  if [ -x "./verify_web_runtime.sh" ]; then
    ./verify_web_runtime.sh || true
  fi
else
  echo "Start failed. Check: $LOG_FILE"
  exit 1
fi
