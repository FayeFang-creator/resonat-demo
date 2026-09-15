# 单镜像部署：构建前端 -> 和后端一起由 serve.py 从同一个源站供出。
# 目标是 Hugging Face Spaces（Docker SDK，默认端口 7860），普通容器平台同样可跑。
#
#   docker build -t sounds-like-you .
#   docker run -p 7860:7860 sounds-like-you
#
# 不需要任何 API key：Cyanite 已下线，检索走仓库内的本地曲库，
# 音频由 Jamendo 公开 CDN 直供浏览器。

# ---------- 1. 构建前端 ----------
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---------- 2. 运行时 ----------
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# HF Spaces 以非 root 用户跑容器；uv 需要能写自己的缓存目录
RUN useradd -m -u 1000 app
USER app
ENV HOME=/home/app \
    PATH=/home/app/.local/bin:$PATH \
    UV_PROJECT_ENVIRONMENT=/home/app/.venv \
    PYTHONUNBUFFERED=1
WORKDIR /home/app/src

# 依赖层单独缓存：只有 pyproject/uv.lock 变了才重装
COPY --chown=app:app backend/pyproject.toml backend/uv.lock ./backend/
RUN uv sync --project backend --frozen --no-dev

COPY --chown=app:app backend/ ./backend/
COPY --chown=app:app serve.py ./
COPY --from=frontend --chown=app:app /build/dist ./frontend/dist

EXPOSE 7860
CMD ["uv", "run", "--project", "backend", "--no-sync", \
     "uvicorn", "serve:root", "--host", "0.0.0.0", "--port", "7860"]
