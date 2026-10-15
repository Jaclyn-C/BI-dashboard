# 生产镜像：pip 安装项目 + alembic 迁移脚本 + 源码，单 worker 启动
# （调度器是进程内 asyncio 任务，多 worker 会重复同步，见 app/upstream/scheduler.py）
FROM python:3.12-slim

WORKDIR /app
# pip 源可用构建参数覆盖（国内本机构建：--build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple）
ARG PIP_INDEX_URL=https://pypi.org/simple
COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
RUN pip install --no-cache-dir --index-url ${PIP_INDEX_URL} .

RUN useradd --create-home appuser
USER appuser
EXPOSE 8000

# 启动即迁移（幂等），再起服务；.env 不打进镜像，配置全走环境变量（compose env_file）
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
