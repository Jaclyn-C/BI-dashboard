# 多阶段：node 构建 → caddy 托管静态产物。
# Caddy 配置由 compose.prod.yaml 挂载 deploy/Caddyfile（含 /api 反代）。
FROM node:20-slim AS build
RUN npm install -g pnpm@10
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .
RUN pnpm build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
