FROM python:3.12.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 MOODPRINT_HOST=0.0.0.0
WORKDIR /srv/moodprint
RUN pip install --no-cache-dir uv==0.11.14
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN useradd --uid 10001 --create-home moodprint
USER 10001
EXPOSE 8001
HEALTHCHECK --interval=20s --timeout=5s CMD ["/srv/moodprint/.venv/bin/python","-c","import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/api/v1/health/live',timeout=3)"]
CMD ["/srv/moodprint/.venv/bin/python","-m","app"]
