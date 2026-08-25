FROM python:3.14.7-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY partgraph ./partgraph

RUN python -m pip install --upgrade pip && python -m pip install .

EXPOSE 8000

CMD ["uvicorn", "partgraph.main:app", "--host", "0.0.0.0", "--port", "8000"]
