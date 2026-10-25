# Single production image: built SPA + FastAPI on one origin (same-origin cookies/CSRF).
FROM node:22.16.0-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 \
    MOODPRINT_HOST=0.0.0.0 APP_ENV=production STATIC_DIR=/srv/moodprint/static PORT=8001
WORKDIR /srv/moodprint
RUN pip install --no-cache-dir uv==0.11.14
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY --from=frontend /build/dist ./static
RUN useradd --uid 10001 --create-home moodprint
USER 10001
EXPOSE 8001
HEALTHCHECK --interval=20s --timeout=5s CMD ["/srv/moodprint/.venv/bin/python","-c","import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/api/v1/health/live' % os.environ.get('PORT','8001'),timeout=3)"]
CMD ["/srv/moodprint/.venv/bin/python","-m","app"]
