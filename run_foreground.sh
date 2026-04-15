#!/usr/bin/env bash
# 前台启动 BioLab Workbench（便于 Ctrl+C 停止）
# 不自动猜测 conda 环境；请在调用前自行激活正确环境。

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${BIOLAB_PROJECT_DIR:-$SCRIPT_DIR}"
cd "$PROJECT_DIR"

_pick_python() {
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

PY_CMD="$(_pick_python || true)"
if [ -z "$PY_CMD" ]; then
  echo "错误: 未找到 python/python3。请先激活环境。"
  exit 1
fi

if ! "$PY_CMD" -c "import flask" >/dev/null 2>&1; then
  echo "错误: 当前 Python 环境缺少 flask。请先手动 conda activate <你的环境名>。"
  exit 1
fi

echo "当前 Python: $("$PY_CMD" -c 'import sys; print(sys.executable)')"
echo "Flask 版本: $("$PY_CMD" -c 'from importlib.metadata import version; print(version(\"flask\"))')"
echo "前台启动中，按 Ctrl+C 停止..."
exec "$PY_CMD" run.py
