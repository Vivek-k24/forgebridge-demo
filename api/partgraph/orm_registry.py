"""Register every SQLAlchemy ORM model with the shared declarative metadata.

Runtime and Alembic must load the same model set. Importing this module is the
single bootstrap point for model-registration side effects; callers should not
maintain independent lists of domain-model imports.
"""

import partgraph.auth.models  # noqa: F401
import partgraph.intelligence.models  # noqa: F401
import partgraph.knowledge.models  # noqa: F401
# PR 2/5 leaves private readiness tables in the legacy module for PR 3/5.
import partgraph.repair_definition.models  # noqa: F401
import partgraph.repair_memory.models  # noqa: F401
import partgraph.repair_session.models  # noqa: F401
import partgraph.user_vehicle.models  # noqa: F401
import partgraph.vehicle.models  # noqa: F401
