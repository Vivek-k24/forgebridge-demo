from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

COMPUTER_SERVICE_BOUNDARY_ACTION_KEY = "boundary-computer-service-required"
COMPUTER_SERVICE_BOUNDARY_CODE = "computer_service_required"
COMPUTER_SERVICE_BOUNDARY_MESSAGE = (
    "This repair has reached a required computer-dependent service step. "
    "PartGraph does not support vehicle-computer diagnostics, relearn, coding, "
    "programming, calibration, or service-tool operations."
)


@dataclass(frozen=True, slots=True)
class ProcedureBoundaryAction:
    action_key: str
    position: int
    skippable: bool


def is_computer_service_boundary(action_key: str) -> bool:
    return action_key == COMPUTER_SERVICE_BOUNDARY_ACTION_KEY


def validate_computer_service_boundary(
    actions: Iterable[ProcedureBoundaryAction],
) -> None:
    """Validate the reserved terminal marker for required unsupported computer work."""
    ordered = sorted(actions, key=lambda item: item.position)
    boundaries = [
        item for item in ordered if is_computer_service_boundary(item.action_key)
    ]
    if not boundaries:
        return
    if len(boundaries) != 1:
        raise ValueError("A repair procedure may contain at most one computer-service boundary.")

    boundary = boundaries[0]
    if not ordered or boundary.position != ordered[-1].position:
        raise ValueError("The computer-service boundary must be the terminal procedure action.")
    if boundary.skippable:
        raise ValueError("The computer-service boundary cannot be skippable.")
