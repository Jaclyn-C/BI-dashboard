#!/usr/bin/env bash
# teardown.sh — 方案B月末收尾：服务器上备份数据库并下载到本地，校验非空后提示释放
# 用法（Git Bash / Linux / macOS）：bash deploy/teardown.sh root@服务器IP
# 流程见 docs/deployment/按量开关部署手册.md §5——释放前必跑，释放后本地数据不可恢复。
set -euo pipefail
cd "$(dirname "$0")/.."

TARGET=${1:?用法: bash deploy/teardown.sh root@服务器IP}

echo "==> 1/3 服务器上执行数据库备份"
ssh "$TARGET" "cd /opt/partner-dashboard && bash deploy/backup.sh"

echo "==> 2/3 下载全部备份到本地 ./backups/"
mkdir -p backups
scp -q "$TARGET:/opt/partner-dashboard/backups/pd-*.sql.gz" backups/

echo "==> 3/3 校验最新备份非空"
LATEST=$(ls -t backups/pd-*.sql.gz | head -1)
[ -s "$LATEST" ] || { echo "!! 备份文件为空：$LATEST —— 禁止释放实例，先排查 backup.sh"; exit 1; }
echo "    最新备份：$LATEST（$(du -h "$LATEST" | cut -f1)）"

echo
echo "======================================================"
echo " 备份已落地本地，现在可以去控制台释放："
echo "  1. ECS 实例 → 释放"
echo "  2. 弹性公网 IP → 释放（只解绑不释放，闲置 EIP 照收费）"
echo " 下月重建/恢复：docs/deployment/按量开关部署手册.md §6"
echo "======================================================"
