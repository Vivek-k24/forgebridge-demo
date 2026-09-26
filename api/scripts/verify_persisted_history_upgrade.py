from __future__ import annotations

import argparse
import os
from decimal import Decimal
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from sqlalchemy.engine import make_url

BASELINE_REVISION = "0020_catalog_coverage"

USER_ID = UUID("10000000-0000-4000-8000-000000000001")
VEHICLE_ID = UUID("20000000-0000-4000-8000-000000000001")
SESSION_ID = UUID("30000000-0000-4000-8000-000000000001")
EVENT_ID = UUID("40000000-0000-4000-8000-000000000001")
DEVICE_ID = UUID("50000000-0000-4000-8000-000000000001")
LOCATION_ID = UUID("60000000-0000-4000-8000-000000000001")
FASTENER_ID = UUID("70000000-0000-4000-8000-000000000001")
INVENTORY_ID = UUID("80000000-0000-4000-8000-000000000001")
OBSERVATION_ID = UUID("90000000-0000-4000-8000-000000000001")
PHOTO_ID = UUID("a0000000-0000-4000-8000-000000000001")
REQUIREMENT_ID = UUID("b0000000-0000-4000-8000-000000000001")
GARAGE_ITEM_ID = UUID("c0000000-0000-4000-8000-000000000001")

IDENTITY_SNAPSHOT = {
    "year": 2099,
    "make": "Synthetic",
    "model": "Migration Fixture",
    "trim": "CI-only",
}
EVENT_PAYLOAD = {"source": "persisted-history-ci", "synthetic": True}


def _connection_string() -> str:
    raw = os.environ.get("PARTGRAPH_DATABASE_URL")
    if not raw:
        raise RuntimeError("PARTGRAPH_DATABASE_URL is required")
    url = make_url(raw)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("Persisted-history verification requires PostgreSQL")
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def _assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def _revision(connection: psycopg.Connection[dict[str, Any]]) -> str:
    row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    if row is None:
        raise AssertionError("alembic_version is empty")
    return str(row["version_num"])


def seed() -> None:
    with psycopg.connect(_connection_string(), row_factory=dict_row) as connection:
        _assert_equal(_revision(connection), BASELINE_REVISION, "seed revision")

        connection.execute(
            """
            INSERT INTO users (id, email, username, password_hash, is_active)
            VALUES (%s, %s, %s, %s, TRUE)
            """,
            (USER_ID, "persisted-history@example.invalid", "persisted_ci", "synthetic-hash"),
        )
        connection.execute(
            "INSERT INTO user_preferences (user_id, units) VALUES (%s, %s)",
            (USER_ID, "metric"),
        )
        connection.execute(
            """
            INSERT INTO user_vehicles (
                id, user_id, canonical_configuration_id, nickname,
                identity_source, identity_resolution, identity_snapshot
            )
            VALUES (%s, %s, NULL, %s, %s, %s, %s)
            """,
            (
                VEHICLE_ID,
                USER_ID,
                "Persisted fixture vehicle",
                "manual",
                "manual_candidate",
                Jsonb(IDENTITY_SNAPSHOT),
            ),
        )
        connection.execute(
            """
            INSERT INTO repair_sessions (
                id, user_id, user_vehicle_id, title, creation_idempotency_key
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                SESSION_ID,
                USER_ID,
                VEHICLE_ID,
                "Persisted migration fixture",
                "persisted-fixture-create",
            ),
        )
        connection.execute(
            """
            INSERT INTO repair_session_events (
                id, session_id, user_id, sequence, event_type,
                idempotency_key, actor_device_id, payload, created_at
            )
            VALUES (%s, %s, %s, 1, 'session_started', %s, %s, %s, %s)
            """,
            (
                EVENT_ID,
                SESSION_ID,
                USER_ID,
                "persisted-fixture-event-1",
                DEVICE_ID,
                Jsonb(EVENT_PAYLOAD),
                "2026-01-01T00:00:00+00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO repair_session_projections (
                session_id, user_id, status, current_sequence, last_event_id,
                last_event_at, editor_device_id, editor_lease_expires_at
            )
            VALUES (%s, %s, 'active', 1, %s, %s, %s, %s)
            """,
            (
                SESSION_ID,
                USER_ID,
                EVENT_ID,
                "2026-01-01T00:00:00+00:00",
                DEVICE_ID,
                "2026-01-01T00:30:00+00:00",
            ),
        )
        connection.execute(
            """
            INSERT INTO repair_storage_locations (id, user_id, session_id, label, notes)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (LOCATION_ID, USER_ID, SESSION_ID, "Magnetic tray", "CI-only storage memory"),
        )
        connection.execute(
            """
            INSERT INTO repair_fasteners (
                id, user_id, session_id, kind, label, origin, position,
                physical_state, storage_location_id, notes
            )
            VALUES (%s, %s, %s, 'fastener', %s, %s, %s, 'stored', %s, %s)
            """,
            (
                FASTENER_ID,
                USER_ID,
                SESSION_ID,
                "Synthetic flange bolt",
                "upper support",
                "left side",
                LOCATION_ID,
                "CI-only fastener memory",
            ),
        )
        connection.execute(
            """
            INSERT INTO repair_inventory_items (
                id, user_id, session_id, name, quantity,
                procurement_state, reference, notes
            )
            VALUES (%s, %s, %s, %s, 1, 'available', %s, %s)
            """,
            (
                INVENTORY_ID,
                USER_ID,
                SESSION_ID,
                "Synthetic 10 mm socket",
                "CI-ONLY",
                "Persisted session inventory",
            ),
        )
        connection.execute(
            """
            INSERT INTO repair_observations (
                id, user_id, session_id, category, text,
                source, review_state, fastener_id
            )
            VALUES (%s, %s, %s, 'general', %s, 'user', 'confirmed', %s)
            """,
            (
                OBSERVATION_ID,
                USER_ID,
                SESSION_ID,
                "Synthetic persisted repair observation",
                FASTENER_ID,
            ),
        )
        connection.execute(
            """
            INSERT INTO repair_photo_evidence (
                id, user_id, session_id, purpose, observation_id, fastener_id,
                storage_key, original_filename, media_type, byte_size, sha256
            )
            VALUES (%s, %s, %s, 'general', %s, %s, %s, %s, 'image/jpeg', 1234, %s)
            """,
            (
                PHOTO_ID,
                USER_ID,
                SESSION_ID,
                OBSERVATION_ID,
                FASTENER_ID,
                "persisted-history/fixture.jpg",
                "fixture.jpg",
                "a" * 64,
            ),
        )
        connection.execute(
            """
            INSERT INTO requirement_definitions (
                id, requirement_key, category, display_name, default_unit
            )
            VALUES (%s, %s, 'tool', %s, 'each')
            """,
            (
                REQUIREMENT_ID,
                "tool.ci.persisted-history",
                "Synthetic persisted-history tool",
            ),
        )
        connection.execute(
            """
            INSERT INTO user_garage_inventory_items (
                id, user_id, requirement_definition_id,
                quantity_available, unit, notes
            )
            VALUES (%s, %s, %s, 2, 'each', %s)
            """,
            (
                GARAGE_ITEM_ID,
                USER_ID,
                REQUIREMENT_ID,
                "CI-only Garage inventory",
            ),
        )

    print("Seeded synthetic persisted-history owner state at revision 0020_catalog_coverage.")


def _fetch_required(
    connection: psycopg.Connection[dict[str, Any]],
    query: str,
    params: tuple[object, ...],
    label: str,
) -> dict[str, Any]:
    row = connection.execute(query, params).fetchone()
    if row is None:
        raise AssertionError(f"{label}: expected row is missing")
    return row


def verify(expected_revision: str) -> None:
    with psycopg.connect(_connection_string(), row_factory=dict_row) as connection:
        _assert_equal(_revision(connection), expected_revision, "upgraded revision")

        user = _fetch_required(
            connection,
            """
            SELECT email, username, password_hash, is_active, role
            FROM users WHERE id = %s
            """,
            (USER_ID,),
            "user",
        )
        _assert_equal(
            dict(user),
            {
                "email": "persisted-history@example.invalid",
                "username": "persisted_ci",
                "password_hash": "synthetic-hash",
                "is_active": True,
                "role": "owner",
            },
            "user values",
        )

        preference = _fetch_required(
            connection,
            "SELECT units FROM user_preferences WHERE user_id = %s",
            (USER_ID,),
            "preference",
        )
        _assert_equal(preference["units"], "metric", "preference units")

        vehicle = _fetch_required(
            connection,
            """
            SELECT nickname, canonical_configuration_id, identity_source,
                   identity_resolution, identity_snapshot
            FROM user_vehicles WHERE id = %s
            """,
            (VEHICLE_ID,),
            "vehicle",
        )
        _assert_equal(vehicle["nickname"], "Persisted fixture vehicle", "vehicle nickname")
        _assert_equal(vehicle["canonical_configuration_id"], None, "vehicle canonical id")
        _assert_equal(vehicle["identity_source"], "manual", "vehicle identity source")
        _assert_equal(vehicle["identity_resolution"], "manual_candidate", "vehicle resolution")
        _assert_equal(vehicle["identity_snapshot"], IDENTITY_SNAPSHOT, "vehicle identity snapshot")

        repair_session = _fetch_required(
            connection,
            """
            SELECT title, creation_idempotency_key, repair_definition_id, archived_at
            FROM repair_sessions WHERE id = %s
            """,
            (SESSION_ID,),
            "repair session",
        )
        _assert_equal(repair_session["title"], "Persisted migration fixture", "session title")
        _assert_equal(
            repair_session["creation_idempotency_key"],
            "persisted-fixture-create",
            "session creation key",
        )
        _assert_equal(repair_session["repair_definition_id"], None, "session repair definition")
        _assert_equal(repair_session["archived_at"], None, "session archived state")

        event = _fetch_required(
            connection,
            """
            SELECT sequence, event_type, idempotency_key, actor_device_id, payload
            FROM repair_session_events WHERE id = %s
            """,
            (EVENT_ID,),
            "repair event",
        )
        _assert_equal(event["sequence"], 1, "event sequence")
        _assert_equal(event["event_type"], "session_started", "event type")
        _assert_equal(event["idempotency_key"], "persisted-fixture-event-1", "event key")
        _assert_equal(event["actor_device_id"], DEVICE_ID, "event device")
        _assert_equal(event["payload"], EVENT_PAYLOAD, "event payload")

        projection = _fetch_required(
            connection,
            """
            SELECT status, current_sequence, last_event_id, editor_device_id
            FROM repair_session_projections WHERE session_id = %s
            """,
            (SESSION_ID,),
            "repair projection",
        )
        _assert_equal(projection["status"], "active", "projection status")
        _assert_equal(projection["current_sequence"], 1, "projection sequence")
        _assert_equal(projection["last_event_id"], EVENT_ID, "projection event")
        _assert_equal(projection["editor_device_id"], DEVICE_ID, "projection device")

        location = _fetch_required(
            connection,
            "SELECT label, notes FROM repair_storage_locations WHERE id = %s",
            (LOCATION_ID,),
            "storage location",
        )
        _assert_equal(location["label"], "Magnetic tray", "storage label")
        _assert_equal(location["notes"], "CI-only storage memory", "storage notes")

        fastener = _fetch_required(
            connection,
            """
            SELECT kind, label, origin, position, physical_state,
                   storage_location_id, notes, hardware_definition_id
            FROM repair_fasteners WHERE id = %s
            """,
            (FASTENER_ID,),
            "fastener",
        )
        _assert_equal(fastener["kind"], "fastener", "fastener kind")
        _assert_equal(fastener["label"], "Synthetic flange bolt", "fastener label")
        _assert_equal(fastener["origin"], "upper support", "fastener origin")
        _assert_equal(fastener["position"], "left side", "fastener position")
        _assert_equal(fastener["physical_state"], "stored", "fastener state")
        _assert_equal(fastener["storage_location_id"], LOCATION_ID, "fastener storage")
        _assert_equal(fastener["notes"], "CI-only fastener memory", "fastener notes")
        _assert_equal(fastener["hardware_definition_id"], None, "legacy fastener hardware link")

        inventory = _fetch_required(
            connection,
            """
            SELECT name, quantity, procurement_state, reference, notes
            FROM repair_inventory_items WHERE id = %s
            """,
            (INVENTORY_ID,),
            "repair inventory",
        )
        _assert_equal(inventory["name"], "Synthetic 10 mm socket", "inventory name")
        _assert_equal(inventory["quantity"], 1, "inventory quantity")
        _assert_equal(inventory["procurement_state"], "available", "inventory state")
        _assert_equal(inventory["reference"], "CI-ONLY", "inventory reference")
        _assert_equal(inventory["notes"], "Persisted session inventory", "inventory notes")

        observation = _fetch_required(
            connection,
            """
            SELECT category, text, source, review_state, fastener_id
            FROM repair_observations WHERE id = %s
            """,
            (OBSERVATION_ID,),
            "observation",
        )
        _assert_equal(observation["category"], "general", "observation category")
        _assert_equal(
            observation["text"],
            "Synthetic persisted repair observation",
            "observation text",
        )
        _assert_equal(observation["source"], "user", "observation source")
        _assert_equal(observation["review_state"], "confirmed", "observation review")
        _assert_equal(observation["fastener_id"], FASTENER_ID, "observation fastener")

        photo = _fetch_required(
            connection,
            """
            SELECT purpose, observation_id, fastener_id, storage_key,
                   original_filename, media_type, byte_size, sha256, deleted_at
            FROM repair_photo_evidence WHERE id = %s
            """,
            (PHOTO_ID,),
            "photo evidence",
        )
        _assert_equal(photo["purpose"], "general", "photo purpose")
        _assert_equal(photo["observation_id"], OBSERVATION_ID, "photo observation")
        _assert_equal(photo["fastener_id"], FASTENER_ID, "photo fastener")
        _assert_equal(photo["storage_key"], "persisted-history/fixture.jpg", "photo storage")
        _assert_equal(photo["original_filename"], "fixture.jpg", "photo filename")
        _assert_equal(photo["media_type"], "image/jpeg", "photo media type")
        _assert_equal(photo["byte_size"], 1234, "photo size")
        _assert_equal(photo["sha256"], "a" * 64, "photo hash")
        _assert_equal(photo["deleted_at"], None, "photo deleted state")

        requirement = _fetch_required(
            connection,
            """
            SELECT requirement_key, category, display_name, default_unit
            FROM requirement_definitions WHERE id = %s
            """,
            (REQUIREMENT_ID,),
            "requirement definition",
        )
        _assert_equal(requirement["requirement_key"], "tool.ci.persisted-history", "requirement key")
        _assert_equal(requirement["category"], "tool", "requirement category")
        _assert_equal(
            requirement["display_name"],
            "Synthetic persisted-history tool",
            "requirement display",
        )
        _assert_equal(requirement["default_unit"], "each", "requirement unit")

        garage = _fetch_required(
            connection,
            """
            SELECT quantity_available, unit, notes
            FROM user_garage_inventory_items WHERE id = %s
            """,
            (GARAGE_ITEM_ID,),
            "Garage inventory",
        )
        _assert_equal(garage["quantity_available"], Decimal("2.000"), "Garage quantity")
        _assert_equal(garage["unit"], "each", "Garage unit")
        _assert_equal(garage["notes"], "CI-only Garage inventory", "Garage notes")

        obsolete_count = connection.execute(
            """
            SELECT count(*) AS count
            FROM equipment_catalog_items
            WHERE catalog_key IN (
                'a-c-refrigerant-recovery-recharge-machine',
                'service-information-wiring-reference'
            )
            """
        ).fetchone()
        if obsolete_count is None:
            raise AssertionError("equipment catalog count query returned no row")
        _assert_equal(obsolete_count["count"], 0, "obsolete equipment rows")

        specific_count = connection.execute(
            """
            SELECT count(*) AS count
            FROM equipment_catalog_items
            WHERE catalog_key IN (
                'r-134a-a-c-refrigerant-recover-recycle-recharge-machine',
                'r-1234yf-a-c-refrigerant-recover-recycle-recharge-machine',
                'r-134a-r-1234yf-dual-refrigerant-a-c-service-machine',
                'r-744-co2-a-c-recharge-service-station'
            )
            """
        ).fetchone()
        if specific_count is None:
            raise AssertionError("specific equipment catalog count query returned no row")
        _assert_equal(specific_count["count"], 4, "specific refrigerant service machines")

    print(
        "Persisted-history upgrade preserved synthetic owner state and reached "
        f"{expected_revision}."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("seed", "verify"))
    parser.add_argument("--expected-revision")
    args = parser.parse_args()

    if args.mode == "seed":
        if args.expected_revision:
            parser.error("--expected-revision is only valid with verify")
        seed()
        return

    if not args.expected_revision:
        parser.error("verify requires --expected-revision")
    verify(args.expected_revision)


if __name__ == "__main__":
    main()
