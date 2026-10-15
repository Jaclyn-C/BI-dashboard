#!/usr/bin/env bash
# deploy.sh — 本地一键部署/升级：打包代码 → ssh 上传 → 服务器执行 setup-server.sh
# 用法（Git Bash / Linux / macOS）：bash deploy/deploy.sh root@服务器IP
# 服务器上已有的 .env、数据库与证书不受影响；升级与首次部署是同一条命令。
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET=${1:?用法: bash deploy/deploy.sh root@服务器IP}
REMOTE_DIR=/opt/partner-dashboard

echo "==> 上传代码到 ${TARGET}:${REMOTE_DIR}（本地 .env、data/ 等不上传）"
tar --exclude=.git \
    --exclude=node_modules \
    --exclude=dist \
    --exclude=__pycache__ \
    --exclude=.venv \
    --exclude=data \
    --exclude='*.egg-info' \
    --exclude=.env \
    --exclude=.env.prod \
    --exclude=backups \
    --exclude=.claude \
    -cf - . | ssh "$TARGET" "mkdir -p ${REMOTE_DIR} && tar -xf - -C ${REMOTE_DIR}"

echo "==> 在服务器上执行部署脚本"
ssh "$TARGET" "cd ${REMOTE_DIR} && bash deploy/setup-server.sh"
