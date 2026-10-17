#!/usr/bin/env bash
# setup-server.sh — 服务器端一键部署（幂等，可重复执行）
# 由本地 deploy/deploy.sh 调用，也可登录服务器手动运行：bash deploy/setup-server.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# 1/5 Docker（已装则跳过）
if ! command -v docker >/dev/null 2>&1; then
  echo "==> 1/5 安装 Docker"
  curl -fsSL https://get.docker.com | sh
else
  echo "==> 1/5 Docker 已安装，跳过"
fi
systemctl enable --now docker 2>/dev/null || true

# 2/5 .env：首次自动生成并填好三个随机密钥；已存在则不动（密钥一经使用不可更换）
if [ ! -f .env ]; then
  echo "==> 2/5 生成 .env（SECRET_KEY / ORDER_FILTER_SALT / POSTGRES_PASSWORD 已自动随机）"
  cp .env.prod.example .env
  SECRET=$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-43)
  SALT=$(openssl rand -hex 12)
  PGPASS=$(openssl rand -hex 16)
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET}|; \
          s|^ORDER_FILTER_SALT=.*|ORDER_FILTER_SALT=${SALT}|; \
          s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PGPASS}|" .env
else
  echo "==> 2/5 .env 已存在，保留"
fi

# 3/5 国内节点网络兜底：Docker Hub / 官方 PyPI 直连超时（2026-10-17 杭州实测），
#     基础镜像缺失时从国内镜像源（daocloud，均为官方 library 镜像）拉取后改回原名；
#     pip 源探测官方源，3 秒不通即回退阿里云 PyPI（调用方显式传入的 PIP_INDEX_URL 优先）
grep -h '^FROM' backend/Dockerfile frontend/Dockerfile | awk '{print $2}' | sort -u | while read -r img; do
  if ! docker image inspect "$img" >/dev/null 2>&1; then
    echo "==> 3/5 基础镜像 ${img} 缺失，走国内镜像源"
    docker pull "docker.m.daocloud.io/library/${img}"
    docker tag "docker.m.daocloud.io/library/${img}" "$img"
    docker rmi "docker.m.daocloud.io/library/${img}" >/dev/null
  fi
done
export PIP_INDEX_URL=${PIP_INDEX_URL:-$(curl -sf -m 3 -o /dev/null https://pypi.org/simple/ \
  && echo https://pypi.org/simple || echo https://mirrors.aliyun.com/pypi/simple)}
echo "==> 3/5 pip 源：${PIP_INDEX_URL}"

# 4/5 必填检查：DOMAIN 为空 Caddy 起不来；SMTP/上游空只影响功能不影响启动
DOMAIN_VAL=$(sed -n 's|^DOMAIN=\(.*\)$|\1|p' .env | head -1 | tr -d ' ')
[ -n "$DOMAIN_VAL" ] || { echo "!! 请先编辑 $(pwd)/.env，把 DOMAIN= 填成访问地址（无域名填 http://<EIP>）"; exit 1; }
if grep -qE '^(SMTP_HOST|UPSTREAM_CLIENT_ID)=$' .env; then
  echo "==> 提示：SMTP_HOST / UPSTREAM_CLIENT_ID 还没填——验证码邮件与订单同步不可用，但不影响启动"
fi

# 5/5 构建并启动（首次构建要几分钟）
echo "==> 5/5 构建并启动"
docker compose -f compose.prod.yaml up -d --build

# 就绪探测：DOMAIN 为 http://<EIP> 时 Caddy 按 Host 匹配站点，必须带上 Host 头访问本机
HOSTPART=${DOMAIN_VAL#http://}; HOSTPART=${HOSTPART#https://}
HOSTPART=${HOSTPART%%/*}; HOSTPART=${HOSTPART%%:*}
probe() {
  if [ -n "$HOSTPART" ]; then
    curl -sf -H "Host: ${HOSTPART}" http://127.0.0.1/healthz >/dev/null 2>&1
  else
    curl -sf http://127.0.0.1/healthz >/dev/null 2>&1
  fi
}
echo "==> 等待服务就绪"
for i in $(seq 1 30); do
  sleep 2
  probe && break
done
if ! probe; then
  echo "!! 服务未就绪，看日志排查：docker compose -f compose.prod.yaml logs api web"
  docker compose -f compose.prod.yaml ps
  exit 1
fi

docker compose -f compose.prod.yaml ps
echo
echo "======================================================"
echo " 部署完成：${DOMAIN_VAL}"
echo " 首次使用：打开网站 → 注册 → 邮箱收验证码（需已配 SMTP）"
echo " 备份/升级/排障：docs/deployment/按量开关部署手册.md"
echo "======================================================"
