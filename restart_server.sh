#!/usr/bin/env bash
# 重启 BioLab Workbench 服务器（端口 5000）
# 不自动猜测 conda 环境；请在调用前自行激活正确环境。

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${BIOLAB_PROJECT_DIR:-$SCRIPT_DIR}"
cd "$PROJECT_DIR"

echo "正在停止旧服务器..."
pkill -f "python.*run.py" || true
sleep 1

if pgrep -f "python.*run.py" >/dev/null 2>&1; then
  echo "检测到 run.py 仍在运行（可能被 PM2 自动拉起）。"
  echo "请先执行: pm2 stop all 或 pm2 stop <run.py对应进程>"
  exit 1
fi

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

echo "检查当前环境..."

PY_CMD="$(_pick_python || true)"
if [ -z "$PY_CMD" ]; then
  echo "错误: 未找到 python/python3。请先激活环境。"
  exit 1
fi

if ! "$PY_CMD" -c "import flask" >/dev/null 2>&1; then
  echo "错误: 当前 Python 环境缺少 flask。"
  echo "当前 Python: $("$PY_CMD" -V 2>&1)"
  echo "请先手动激活环境后重试（例如: conda activate <你的环境名>）。"
  exit 1
fi

echo "当前解释器路径: $("$PY_CMD" -c 'import sys; print(sys.executable)')"
echo "Flask 版本: $("$PY_CMD" -c 'from importlib.metadata import version; print(version(\"flask\"))')"
echo "正在启动新服务器..."
nohup "$PY_CMD" run.py > server.log 2>&1 &
sleep 2

if pgrep -f "python.*run.py" >/dev/null 2>&1; then
  echo "服务器已启动！"
  echo "查看日志: tail -f server.log"
  echo "访问地址: http://100.117.136.47:5000/sequence"
  if [ -x "./verify_web_runtime.sh" ]; then
    ./verify_web_runtime.sh || true
  fi
else
  echo "启动失败，请查看日志: tail -n 80 server.log"
  exit 1
fi
