FROM python:3.14.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY migrations ./migrations
COPY partgraph ./partgraph

RUN python -m pip install --upgrade pip && \
    python -m pip install . && \
    useradd --create-home --uid 10001 --shell /usr/sbin/nologin partgraph && \
    mkdir -p /app/media && \
    chown -R partgraph:partgraph /app

USER partgraph

EXPOSE 8000

CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && exec uvicorn partgraph.main:app --host 0.0.0.0 --port 8000"]
