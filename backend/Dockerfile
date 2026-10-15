# 生产镜像：Python 3.12 slim；依赖唯一真源 pyproject.toml（pip install .）。
# 启动：先幂等跑 Alembic 迁移，再起 uvicorn（演示规模单进程足够）。
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
