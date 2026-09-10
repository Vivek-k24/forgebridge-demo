from partgraph.knowledge.reference_fleet import (
    EXPECTED_MVP_DOMAINS,
    load_reference_fleet,
)
from partgraph.knowledge.support_boundaries import (
    COMPUTER_SERVICE_BOUNDARY_ACTION_KEY,
    ProcedureBoundaryAction,
    is_computer_service_boundary,
    validate_computer_service_boundary,
)


def test_reference_fleet_has_five_source_backed_configurations_and_full_domain_mix() -> None:
    payload = load_reference_fleet()

    assert len(payload["vehicles"]) == 5
    assert payload["product_rules"]["computer_service"] == "unsupported_indefinitely"
    assert payload["product_rules"]["guided_physical_bleeding"] is True

    covered = {
        domain
        for vehicle in payload["vehicles"]
        for domain in vehicle["mvp_domains"]
    }
    assert covered == EXPECTED_MVP_DOMAINS
    assert all(vehicle["evidence"] for vehicle in payload["vehicles"])


def test_computer_service_boundary_is_reserved_terminal_non_skippable_action() -> None:
    actions = [
        ProcedureBoundaryAction(action_key="remove-component", position=0, skippable=False),
        ProcedureBoundaryAction(action_key="install-component", position=1, skippable=False),
        ProcedureBoundaryAction(
            action_key=COMPUTER_SERVICE_BOUNDARY_ACTION_KEY,
            position=2,
            skippable=False,
        ),
    ]

    validate_computer_service_boundary(actions)
    assert is_computer_service_boundary(COMPUTER_SERVICE_BOUNDARY_ACTION_KEY)
    assert not is_computer_service_boundary("bleed-brakes")


def test_computer_service_boundary_cannot_be_hidden_in_middle_of_procedure() -> None:
    actions = [
        ProcedureBoundaryAction(
            action_key=COMPUTER_SERVICE_BOUNDARY_ACTION_KEY,
            position=0,
            skippable=False,
        ),
        ProcedureBoundaryAction(action_key="verify-repair", position=1, skippable=False),
    ]

    try:
        validate_computer_service_boundary(actions)
    except ValueError as exc:
        assert "terminal" in str(exc)
    else:
        raise AssertionError("non-terminal computer-service boundary was accepted")


def test_computer_service_boundary_can_never_be_skippable() -> None:
    actions = [
        ProcedureBoundaryAction(
            action_key=COMPUTER_SERVICE_BOUNDARY_ACTION_KEY,
            position=0,
            skippable=True,
        )
    ]

    try:
        validate_computer_service_boundary(actions)
    except ValueError as exc:
        assert "skippable" in str(exc)
    else:
        raise AssertionError("skippable computer-service boundary was accepted")
