#!/usr/bin/env bash
# backup.sh — 每日数据库备份：pg_dump 到服务器 /opt/partner-dashboard/backups/，保留最近 14 份
# 服务器上配一次定时（按量开关部署手册 §5）：crontab -e 加一行
#   10 4 * * * bash /opt/partner-dashboard/deploy/backup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p backups
FILE="backups/pd-$(date +%F).sql.gz"
docker compose -f compose.prod.yaml exec -T postgres pg_dump -U pd pd | gzip > "$FILE"
ls -t backups/pd-*.sql.gz | tail -n +15 | xargs -r rm -f
echo "备份完成：${FILE}（$(du -h "$FILE" | cut -f1)）"
