from partgraph.knowledge.reference_fleet import (
    EXPECTED_MVP_DOMAINS,
    load_reference_fleet,
)
from partgraph.knowledge.reference_fleet_repairs import (
    DEFERRED_GUIDED_OPERATIONS,
    load_reference_fleet_repair_corpus,
    verified_reference_repairs,
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


def test_reference_repair_corpus_does_not_inherit_collector_rules() -> None:
    payload = load_reference_fleet_repair_corpus()
    policy = payload["verification_policy"]

    assert policy["collector_rules_inherited"] is False
    assert policy["computer_service"] == "unsupported_indefinitely"
    assert policy["physical_bleeding_supported"] is True
    assert set(policy["deferred_guided_operations"]) == DEFERRED_GUIDED_OPERATIONS


def test_only_verified_reference_repairs_expose_guided_actions() -> None:
    payload = load_reference_fleet_repair_corpus()
    verified = verified_reference_repairs()

    assert verified
    assert all(repair["actions"] for repair in verified)
    assert all(
        not repair["actions"]
        for repair in payload["repairs"]
        if repair["verification_status"] == "candidate"
    )


def test_reference_repair_corpus_contains_all_planned_mvp_domains() -> None:
    payload = load_reference_fleet_repair_corpus()
    covered = {
        domain
        for repair in payload["repairs"]
        for domain in repair["domains"]
    }

    # A domain may be present as candidate research before it is safe to guide.
    assert EXPECTED_MVP_DOMAINS.issubset(covered)


def test_verified_reference_actions_do_not_guide_deferred_operations() -> None:
    for repair in verified_reference_repairs():
        for action in repair["actions"]:
            text = " ".join(
                f"{action['key']} {action['title']} {action['instruction']}"
                .casefold()
                .replace("-", " ")
                .replace("_", " ")
                .split()
            )
            assert not any(operation in text for operation in DEFERRED_GUIDED_OPERATIONS)


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
