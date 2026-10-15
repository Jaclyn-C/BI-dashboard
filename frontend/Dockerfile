# 生产镜像：pnpm 构建 → Caddy 托管静态产物（Caddyfile 由 compose 挂载，改域名无需重建）
FROM node:20-alpine AS build
WORKDIR /app
RUN npm install -g pnpm@12
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile --allow-build=esbuild
COPY . .
RUN pnpm build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
