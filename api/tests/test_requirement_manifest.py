from decimal import Decimal
from uuid import uuid4

import pytest

from partgraph.repair_definition.manifest import (
    ManifestConflict,
    RequirementFact,
    build_requirement_manifest,
)


def fact(
    key: str,
    *,
    category: str,
    name: str,
    quantity: str | None,
    unit: str | None,
    mode: str,
    operation: str,
    necessity: str = "required",
) -> RequirementFact:
    return RequirementFact(
        use_id=uuid4(),
        requirement_key=key,
        category=category,
        display_name=name,
        quantity=Decimal(quantity) if quantity is not None else None,
        unit=unit,
        necessity=necessity,
        fulfillment_mode=mode,
        timing="operation",
        operation_key=operation,
    )


def test_reusable_tool_used_by_multiple_operations_is_not_double_counted() -> None:
    manifest = build_requirement_manifest(
        [
            fact(
                "tool.socket.10mm",
                category="tool",
                name="10 mm socket",
                quantity="1",
                unit="each",
                mode="reusable",
                operation="remove_support",
            ),
            fact(
                "tool.socket.10mm",
                category="tool",
                name="10 mm socket",
                quantity="1",
                unit="each",
                mode="reusable",
                operation="remove_bracket",
            ),
        ]
    )

    assert len(manifest) == 1
    assert manifest[0].required_quantity == Decimal("1")
    assert manifest[0].operation_keys == ("remove_bracket", "remove_support")


def test_consumed_hardware_quantities_sum() -> None:
    manifest = build_requirement_manifest(
        [
            fact(
                "hardware.clip.example",
                category="hardware",
                name="Example one-time clip",
                quantity="2",
                unit="each",
                mode="consumed",
                operation="remove_left_cover",
            ),
            fact(
                "hardware.clip.example",
                category="hardware",
                name="Example one-time clip",
                quantity="2",
                unit="each",
                mode="consumed",
                operation="remove_right_cover",
            ),
        ]
    )

    assert manifest[0].required_quantity == Decimal("4")


def test_unknown_quantity_remains_unknown_instead_of_being_guessed() -> None:
    manifest = build_requirement_manifest(
        [
            fact(
                "consumable.shop_towel",
                category="consumable",
                name="Shop towels",
                quantity=None,
                unit=None,
                mode="consumed",
                operation="prepare_workspace",
            )
        ]
    )

    assert manifest[0].required_quantity is None


def test_required_use_dominates_recommended_use() -> None:
    manifest = build_requirement_manifest(
        [
            fact(
                "equipment.drain_pan",
                category="equipment",
                name="Drain pan",
                quantity="1",
                unit="each",
                mode="reusable",
                operation="prepare_workspace",
                necessity="recommended",
            ),
            fact(
                "equipment.drain_pan",
                category="equipment",
                name="Drain pan",
                quantity="1",
                unit="each",
                mode="reusable",
                operation="drain_fluid",
            ),
        ]
    )

    assert manifest[0].necessity == "required"


def test_unit_conflict_is_not_silently_converted() -> None:
    with pytest.raises(ManifestConflict, match="unit conflict"):
        build_requirement_manifest(
            [
                fact(
                    "fluid.example",
                    category="fluid",
                    name="Example fluid",
                    quantity="1",
                    unit="quart",
                    mode="consumed",
                    operation="fill",
                ),
                fact(
                    "fluid.example",
                    category="fluid",
                    name="Example fluid",
                    quantity="1",
                    unit="liter",
                    mode="consumed",
                    operation="top_off",
                ),
            ]
        )


def test_conflicting_fulfillment_semantics_require_review() -> None:
    with pytest.raises(ManifestConflict, match="fulfillment conflict"):
        build_requirement_manifest(
            [
                fact(
                    "hardware.example_bolt",
                    category="hardware",
                    name="Example bolt",
                    quantity="1",
                    unit="each",
                    mode="reuse_existing",
                    operation="remove",
                ),
                fact(
                    "hardware.example_bolt",
                    category="hardware",
                    name="Example bolt",
                    quantity="1",
                    unit="each",
                    mode="replacement_required",
                    operation="install",
                ),
            ]
        )
