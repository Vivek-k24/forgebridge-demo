import os

# FastAPI TestClient and several deterministic helpers intentionally create
# separate event loops during the suite. Reusing async psycopg connections
# across those loops is invalid, so tests use one connection per checkout.
# Production keeps SQLAlchemy pooling enabled by default.
os.environ.setdefault("PARTGRAPH_DATABASE_POOLING", "false")
