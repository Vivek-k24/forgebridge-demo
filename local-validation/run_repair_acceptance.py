"""Bootstrap the local repair acceptance runner with the canonical ORM registry.

The acceptance runner inserts synthetic canonical repair rows directly through SQLAlchemy.
Load the same complete model registry used by Alembic/runtime before those inserts so
foreign-key dependency ordering can resolve every mapped target table.
"""

import runpy

import partgraph.orm_registry  # noqa: F401

runpy.run_path("local-validation/acceptance_runner.py", run_name="__main__")
