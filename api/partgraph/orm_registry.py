"""Register every SQLAlchemy ORM model with the shared declarative metadata.

Runtime and Alembic must load the same model set. Importing this module is the
single bootstrap point for model-registration side effects; callers should not
maintain independent lists of domain-model imports.
"""

import partgraph.equipment.models  # noqa: F401
import partgraph.identity.auth.models  # noqa: F401
import partgraph.identity.user_vehicle.models  # noqa: F401
import partgraph.identity.vehicle.models  # noqa: F401
import partgraph.intelligence.models  # noqa: F401
import partgraph.knowledge.capability  # noqa: F401
import partgraph.knowledge.completion_models  # noqa: F401
import partgraph.knowledge.coverage_models  # noqa: F401
import partgraph.knowledge.diagnostics  # noqa: F401
import partgraph.knowledge.electrical  # noqa: F401
import partgraph.knowledge.fitment  # noqa: F401
import partgraph.knowledge.hardware  # noqa: F401
import partgraph.knowledge.interchange  # noqa: F401
import partgraph.knowledge.materials  # noqa: F401
import partgraph.knowledge.models  # noqa: F401
import partgraph.knowledge.parts  # noqa: F401
import partgraph.knowledge.relationships  # noqa: F401
import partgraph.knowledge.requirements  # noqa: F401
import partgraph.knowledge.specifications  # noqa: F401
import partgraph.knowledge.vehicle_structure  # noqa: F401
import partgraph.operator.models  # noqa: F401
import partgraph.repair_experience.completion_models  # noqa: F401
import partgraph.repair_experience.memory_models  # noqa: F401
import partgraph.repair_experience.models  # noqa: F401
import partgraph.repair_experience.readiness_models  # noqa: F401
