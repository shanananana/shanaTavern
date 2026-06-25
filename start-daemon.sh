#!/bin/bash
# 后台稳定启动 TavernMixer + ngrok 隧道
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
LOG="/tmp/tavernmixer.log"
NGROK_LOG="/tmp/tavernmixer-ngrok.log"
PIDFILE="/tmp/tavernmixer.pid"
NGROK_PIDFILE="/tmp/tavernmixer-ngrok.pid"

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
  nohup .venv/bin/uvicorn main:app --host 0.0.0.0 --port 8787 >> "$LOG" 2>&1 &
  echo $! > "$PIDFILE"
  sleep 1
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
start_ngrok

IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "本机IP")
URL=$(ngrok_url)

echo ""
echo "访问地址："
echo "  本机:   http://127.0.0.1:8787"
echo "  局域网: http://${IP}:8787"
if [ -n "$URL" ]; then
  echo "  公网:   $URL"
fi
echo "  ngrok 面板: http://127.0.0.1:4040"
echo "  日志:   $LOG / $NGROK_LOG"
