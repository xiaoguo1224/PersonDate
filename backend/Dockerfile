# ─── deps: 安装依赖 ─────────────────────────────────
FROM python:3.11-slim AS deps

WORKDIR /app
RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ─── production: 运行镜像 ──────────────────────────
FROM python:3.11-slim AS production

WORKDIR /app

# 从 deps 阶段复制已安装的依赖
COPY --from=deps /app/.venv /app/.venv
COPY --from=deps /usr/local/bin/uv /usr/local/bin/uv
ENV PATH=/app/.venv/bin:$PATH

# 复制源码（依赖不变时 deps 层走缓存，此处只复制源码）
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY wechat_channel ./wechat_channel

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
