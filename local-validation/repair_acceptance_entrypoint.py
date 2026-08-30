"""Bootstrap the full PartGraph ORM registry before running repair acceptance cases.

The repair acceptance runner seeds canonical fixture rows directly through SQLAlchemy.
It therefore needs the same complete model-registration bootstrap used by Alembic,
rather than a selective set of model imports.
"""

import runpy

import partgraph.orm_registry  # noqa: F401


if __name__ == "__main__":
    runpy.run_path("local-validation/acceptance_runner.py", run_name="__main__")
