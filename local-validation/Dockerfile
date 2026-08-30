FROM python:3.14.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /work

COPY api ./api
COPY local-validation ./local-validation

RUN python -m pip install --upgrade pip && \
    python -m pip install ./api && \
    python -m pip install httpx==0.28.1

CMD ["python", "local-validation/acceptance_runner.py"]
