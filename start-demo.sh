#!/usr/bin/env bash
# start-demo.sh — 一键启动演示环境（数据库 → 后端 → 前端 → 公网隧道）
# 用法：./start-demo.sh   （重复执行安全：已在跑的服务直接跳过）
set -euo pipefail
cd "$(dirname "$0")"

CLOUDFLARED=/opt/homebrew/opt/cloudflared/bin/cloudflared
BACKEND_DIR=backend
FRONTEND_DIR=frontend
TUNNEL_LOG=/tmp/pd-tunnel.log

echo "==> 1/4 数据库"
docker compose -f compose.dev.yaml up -d
echo "    OK"

echo "==> 2/4 后端 (:8000)"
if lsof -ti:8000 >/dev/null 2>&1; then
  echo "    已在跑，跳过"
else
  (cd "$BACKEND_DIR" && nohup .venv/bin/uvicorn app.main:app --port 8000 > /tmp/pd-backend.log 2>&1 &)
  for i in $(seq 1 15); do curl -sf http://localhost:8000/healthz >/dev/null 2>&1 && break; sleep 1; done
  curl -sf http://localhost:8000/healthz >/dev/null
  echo "    OK（日志: /tmp/pd-backend.log）"
fi

echo "==> 3/4 前端 (vite)"
FRONT_PORT=""
if lsof -ti:5173 >/dev/null 2>&1; then FRONT_PORT=5173
elif lsof -ti:5174 >/dev/null 2>&1; then FRONT_PORT=5174
else
  (cd "$FRONTEND_DIR" && nohup pnpm dev > /tmp/pd-vite.log 2>&1 &)
  for i in $(seq 1 15); do
    sleep 1
    if lsof -ti:5173 >/dev/null 2>&1; then FRONT_PORT=5173; break; fi
    if lsof -ti:5174 >/dev/null 2>&1; then FRONT_PORT=5174; break; fi
  done
fi
[ -n "$FRONT_PORT" ] || { echo "    前端启动失败，看 /tmp/pd-vite.log"; exit 1; }
echo "    OK（端口 $FRONT_PORT，日志: /tmp/pd-vite.log）"

echo "==> 4/4 公网隧道"
if pgrep -f "cloudflared tunnel" >/dev/null 2>&1; then
  echo "    已在跑，跳过"
else
  rm -f "$TUNNEL_LOG"
  (nohup "$CLOUDFLARED" tunnel --url "http://localhost:$FRONT_PORT" > "$TUNNEL_LOG" 2>&1 &)
  for i in $(seq 1 15); do
    sleep 1
    URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
    [ -n "$URL" ] && break
  done
fi
URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
[ -n "$URL" ] || { echo "    隧道启动失败，看 $TUNNEL_LOG"; exit 1; }

echo
echo "=============================================="
echo " 本地访问：http://localhost:$FRONT_PORT"
echo " 公网访问：$URL"
echo " 演示账号：admin@admin.com / admin123"
echo "=============================================="
echo " 关闭全部：./stop-demo.sh   （Mac 合盖/睡眠链接也会断）"
