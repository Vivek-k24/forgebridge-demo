from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


class ManifestConflict(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RequirementFact:
    use_id: UUID
    requirement_key: str
    category: str
    display_name: str
    quantity: Decimal | None
    unit: str | None
    necessity: str
    fulfillment_mode: str
    timing: str
    operation_key: str | None


@dataclass(frozen=True, slots=True)
class ManifestItem:
    requirement_key: str
    category: str
    display_name: str
    required_quantity: Decimal | None
    unit: str | None
    necessity: str
    fulfillment_mode: str
    operation_keys: tuple[str, ...]
    supporting_use_ids: tuple[UUID, ...]


_MAX_AGGREGATION_MODES = {"reusable", "reuse_existing", "replace_if_damaged"}
_SUM_AGGREGATION_MODES = {"consumed", "replacement_required"}


def _aggregate_quantity(facts: list[RequirementFact], fulfillment_mode: str) -> Decimal | None:
    quantities = [fact.quantity for fact in facts]
    if any(quantity is None for quantity in quantities):
        return None

    known_quantities = [quantity for quantity in quantities if quantity is not None]
    if fulfillment_mode in _MAX_AGGREGATION_MODES:
        return max(known_quantities, default=Decimal("0"))
    if fulfillment_mode in _SUM_AGGREGATION_MODES:
        return sum(known_quantities, start=Decimal("0"))
    raise ManifestConflict(f"unknown fulfillment mode: {fulfillment_mode}")


def build_requirement_manifest(facts: list[RequirementFact]) -> tuple[ManifestItem, ...]:
    """Aggregate verified requirement uses without inventing quantities or conversions.

    Reusable/reused/conditional items take the maximum simultaneous quantity.
    Consumed and replacement-required items sum explicit quantities. Any unknown
    quantity keeps the aggregate quantity unknown rather than guessing.
    """

    grouped: dict[str, list[RequirementFact]] = defaultdict(list)
    for fact in facts:
        grouped[fact.requirement_key].append(fact)

    manifest: list[ManifestItem] = []
    for requirement_key in sorted(grouped):
        group = grouped[requirement_key]
        categories = {fact.category for fact in group}
        names = {fact.display_name for fact in group}
        units = {fact.unit for fact in group}
        modes = {fact.fulfillment_mode for fact in group}

        if len(categories) != 1 or len(names) != 1:
            raise ManifestConflict(
                f"requirement definition conflict for {requirement_key}"
            )
        if len(units) != 1:
            raise ManifestConflict(
                f"unit conflict for {requirement_key}; explicit normalization is required"
            )
        if len(modes) != 1:
            raise ManifestConflict(
                f"fulfillment conflict for {requirement_key}; human review is required"
            )

        mode = next(iter(modes))
        necessity = (
            "required"
            if any(fact.necessity == "required" for fact in group)
            else "recommended"
        )
        operation_keys = tuple(
            sorted({fact.operation_key for fact in group if fact.operation_key is not None})
        )
        manifest.append(
            ManifestItem(
                requirement_key=requirement_key,
                category=next(iter(categories)),
                display_name=next(iter(names)),
                required_quantity=_aggregate_quantity(group, mode),
                unit=next(iter(units)),
                necessity=necessity,
                fulfillment_mode=mode,
                operation_keys=operation_keys,
                supporting_use_ids=tuple(sorted((fact.use_id for fact in group), key=str)),
            )
        )

    return tuple(manifest)
