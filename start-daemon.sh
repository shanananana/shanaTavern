#!/bin/bash
# 后台稳定启动 shanaTavern（ngrok 可选，见 .env ENABLE_NGROK）
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG="/tmp/shanatavern.log"
NGROK_LOG="/tmp/shanatavern-ngrok.log"
PIDFILE="/tmp/shanatavern.pid"
NGROK_PIDFILE="/tmp/shanatavern-ngrok.pid"

# 从 .env 读取 ENABLE_NGROK，默认 false
ENABLE_NGROK=false
if [ -f "$ROOT/.env" ]; then
  val=$(grep -E '^ENABLE_NGROK=' "$ROOT/.env" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d ' "'\''')
  [ -n "$val" ] && ENABLE_NGROK="$val"
fi
is_true() {
  case "${1,,}" in true|1|yes|on) return 0 ;; *) return 1 ;; esac
}

ngrok_url() {
  curl -sf --connect-timeout 2 http://127.0.0.1:4040/api/tunnels 2>/dev/null \
    | python3 -c "import json,sys; d=json.load(sys.stdin); ts=d.get('tunnels',[]); print(ts[0]['public_url'] if ts else '')" 2>/dev/null || true
}

start_backend() {
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "后端已在运行 (pid $(cat "$PIDFILE"))"
    return 0
  fi
  if lsof -tiTCP:8787 -sTCP:LISTEN >/dev/null 2>&1; then
    echo "8787 端口已被占用，跳过后端启动"
    return 0
  fi
  cd "$ROOT/backend"
  nohup .venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8787 --timeout-graceful-shutdown 10 >> "$LOG" 2>&1 &
  echo $! > "$PIDFILE"
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    curl -sf --connect-timeout 2 http://127.0.0.1:8787/ >/dev/null && break
    sleep 1
  done
  curl -sf --connect-timeout 2 http://127.0.0.1:8787/ >/dev/null \
    || { echo "后端启动失败: tail -20 $LOG"; exit 1; }
  echo "后端已启动"
}

start_ngrok() {
  if pgrep -x ngrok >/dev/null 2>&1 && curl -sf http://127.0.0.1:4040/api/tunnels >/dev/null 2>&1; then
    echo "ngrok 已在运行"
    return 0
  fi
  if ! command -v ngrok >/dev/null 2>&1; then
    echo "未找到 ngrok，跳过公网隧道"
    return 0
  fi
  pkill -x ngrok 2>/dev/null || true
  sleep 1
  nohup ngrok http 8787 --log=stdout >> "$NGROK_LOG" 2>&1 &
  echo $! > "$NGROK_PIDFILE"
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    URL=$(ngrok_url)
    [ -n "$URL" ] && break
    sleep 1
  done
  if [ -z "$URL" ]; then
    echo "ngrok 启动失败: tail -20 $NGROK_LOG"
    return 1
  fi
  echo "ngrok 已启动"
}

start_backend
if is_true "$ENABLE_NGROK"; then
  start_ngrok
else
  echo "ngrok 未启用（.env 中设置 ENABLE_NGROK=true 可开启）"
fi

IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "本机IP")
URL=""
if is_true "$ENABLE_NGROK"; then
  URL=$(ngrok_url)
fi

echo ""
echo "访问地址："
echo "  本机:   http://127.0.0.1:8787"
echo "  局域网: http://${IP}:8787"
if [ -n "$URL" ]; then
  echo "  公网:   $URL"
  echo "  ngrok 面板: http://127.0.0.1:4040"
fi
echo "  日志:   $LOG"
if is_true "$ENABLE_NGROK"; then
  echo "          $NGROK_LOG"
fi
