#!/usr/bin/env bash
# stop-demo.sh — 关闭演示环境（隧道 + 前端 + 后端；数据库保留，数据不丢）
set -uo pipefail
cd "$(dirname "$0")"

echo "==> 关闭隧道"
pkill -f "cloudflared tunnel" 2>/dev/null && echo "    OK" || echo "    本来就没开"
echo "==> 关闭前端"
lsof -ti:5173 -ti:5174 2>/dev/null | xargs kill 2>/dev/null && echo "    OK" || echo "    本来就没开"
echo "==> 关闭后端"
lsof -ti:8000 2>/dev/null | xargs kill 2>/dev/null && echo "    OK" || echo "    本来就没开"
echo "==> 数据库保留运行（数据不丢；要彻底停：docker compose -f compose.dev.yaml down）"
