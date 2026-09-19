from __future__ import annotations

from .catalog_dataset import load_equipment_category_meta

# Runtime category metadata comes from the same versioned dataset as catalog rows.
# Legacy generator metadata remains only for immutable migration compatibility.
CATEGORY_META = load_equipment_category_meta()
