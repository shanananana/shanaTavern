#!/bin/bash
# 优雅停止 shanaTavern（SIGTERM → uvicorn graceful shutdown）
ROOT="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="/tmp/shanatavern.pid"
NGROK_PIDFILE="/tmp/shanatavern-ngrok.pid"
GRACE="${SHUTDOWN_GRACE_SECONDS:-10}"

stop_pid() {
  local file="$1"
  local name="$2"
  if [ ! -f "$file" ]; then
    echo "$name 未运行（无 pid 文件）"
    return 0
  fi
  local pid
  pid=$(cat "$file")
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "$name 未运行（pid $pid 不存在）"
    rm -f "$file"
    return 0
  fi
  echo "停止 $name (pid $pid, SIGTERM, 最多 ${GRACE}s)..."
  kill -TERM "$pid" 2>/dev/null || true
  for _ in $(seq 1 "$GRACE"); do
    kill -0 "$pid" 2>/dev/null || { echo "$name 已停止"; rm -f "$file"; return 0; }
    sleep 1
  done
  if kill -0 "$pid" 2>/dev/null; then
    echo "$name 未在 ${GRACE}s 内退出，发送 SIGKILL"
    kill -KILL "$pid" 2>/dev/null || true
  fi
  rm -f "$file"
}

stop_pid "$PIDFILE" "后端"
stop_pid "$NGROK_PIDFILE" "ngrok"
pkill -x ngrok 2>/dev/null || true
echo "完成"
