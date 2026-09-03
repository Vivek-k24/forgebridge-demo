"""Add the multi-source 2009 Honda Civic Hybrid reference profile."""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_reference_civic_hybrid_profile"
down_revision: str | None = "0017_selected_asian_workbook"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VEHICLE_ID = UUID("7feb13e9-bca0-5d8b-b701-f0260cce5da1")
PROFILE_ID = UUID("48a527db-2d90-52f9-a9da-0aa761718703")
OLD_IDENTITY_HASH = "31111f85a4f95ba85abbe452c132c20eddd02e0f7242c088e49f1a328bee45cb"
NEW_IDENTITY_HASH = "82a410dc96832dc6014dba8e94dc0e693de67ce4d34e2b4fc0025fe4c902d787"

PROFILE = {
    "identity": {
        "year": 2009,
        "market": "US",
        "make": "Honda",
        "model": "CIVIC",
        "trim": "HYBRID",
        "body_style": "Sedan",
        "doors": 4,
        "seating_capacity": 5,
        "drivetrain": "FWD",
        "transmission": "CVT",
        "canonical_trim_note": (
            "HYBRID is the canonical trim. Leather and navigation were option/package "
            "combinations, not separate canonical PartGraph trims."
        ),
        "generation_note": (
            "Generation is intentionally not used as canonical identity here because "
            "sources may describe the eighth-generation Civic platform or the second-"
            "generation Civic Hybrid lineage."
        ),
    },
    "powertrain": {
        "engine": "1.3L I4 HYBRID",
        "displacement_cc": 1339,
        "cylinders": 4,
        "configuration": "Inline",
        "block_head_material": "Aluminum alloy",
        "compression_ratio": "10.8:1",
        "valvetrain": "8-valve SOHC i-VTEC",
        "drive_by_wire": True,
        "combined_horsepower_hp": 110,
        "horsepower_rpm": 6000,
        "combined_torque_lb_ft": 123,
        "torque_rpm_range": "1000-2500",
        "electric_motor_type": "Permanent magnet",
        "hybrid_battery_chemistry": "Nickel-Metal Hydride (Ni-MH)",
        "hybrid_battery_output_volts": 158,
        "emissions_rating": "AT-PZEV",
        "fuel": "Regular unleaded",
    },
    "efficiency": {
        "epa_city_mpg": 40,
        "epa_highway_mpg": 45,
        "epa_combined_mpg": 42,
        "fuel_tank_gallons": 12.3,
    },
    "dimensions_weight": {
        "wheelbase_in": 106.3,
        "length_in": 177.3,
        "width_in": 69.0,
        "height_in": 56.3,
        "track_front_in": 59.1,
        "track_rear_in": 60.2,
        "curb_weight_lb": 2877,
    },
    "interior": {
        "passenger_volume_cu_ft": 90.9,
        "cargo_volume_cu_ft": 10.4,
        "headroom_front_rear_in": [39.4, 37.4],
        "legroom_front_rear_in": [42.2, 34.6],
        "shoulder_room_front_rear_in": [53.6, 52.3],
        "hiproom_front_rear_in": [51.9, 51.0],
    },
    "chassis": {
        "construction": "Unit-body",
        "front_suspension": "MacPherson strut",
        "rear_suspension": "Multi-link",
        "stabilizer_bar_front_rear_mm": [24.2, 12.0],
        "steering": "Electric power-assisted rack-and-pinion",
        "steering_turns_lock_to_lock": 2.71,
        "turning_diameter_curb_to_curb_ft": 34.8,
        "front_brakes": "10.3 in ventilated disc",
        "rear_brakes": "10.2 in solid disc",
        "wheels": "15 in lightweight alloy",
        "tires": "P195/65 R15 89S",
    },
    "safety": {
        "abs": True,
        "electronic_brake_distribution": True,
        "vehicle_stability_assist": True,
        "traction_control": True,
        "brake_assist": True,
        "tire_pressure_monitoring": True,
        "daytime_running_lights": True,
        "front_airbags": True,
        "front_side_airbags": True,
        "side_curtain_airbags": True,
        "active_front_head_restraints": True,
        "ace_body_structure": True,
        "latch": True,
    },
    "factory_features_options": {
        "automatic_climate_control": True,
        "navigation_available": True,
        "bluetooth_with_navigation": True,
        "leather_trim_available": True,
        "heated_front_seats_with_leather": True,
        "heated_side_mirrors_with_leather": True,
        "rear_decklid_spoiler": True,
        "mirror_turn_indicators": True,
        "audio": "160-watt AM/FM/CD, 6 speakers",
        "usb_audio_interface": True,
    },
    "manufacturer_service_specifications": {
        "engine_bore_stroke_in": [2.87, 3.15],
        "engine_oil_change_with_filter_us_qt": 3.4,
        "engine_oil_change_without_filter_us_qt": 3.2,
        "engine_coolant_change_us_gal": 1.255,
        "engine_coolant_total_us_gal": 1.59,
        "transmission_fluid_change_us_qt": 3.0,
        "transmission_fluid_total_us_qt": 5.4,
        "spark_plugs": ["NGK ILFR6J-11K", "DENSO SK20HPR-L11"],
    },
}

SOURCE_MATRIX = {
    "rule": (
        "Ordinary vehicle identity/specification fields are treated as corroborated "
        "when at least three independent sources agree. Manufacturer-only details are "
        "retained separately as manufacturer-reported rather than silently promoted."
    ),
    "sources": [
        {
            "id": "honda_2009_hybrid_fact_sheet",
            "source_class": "manufacturer",
            "url": (
                "https://automobiles.honda.com/images/2009/civic-hybrid/downloads/"
                "2009-civic-hybrid-factsheet.pdf"
            ),
        },
        {
            "id": "honda_2009_hybrid_owner_manual",
            "source_class": "manufacturer",
            "url": "https://techinfo.honda.com/rjanisis/pubs/OM/NC0909/NC0909OM.pdf",
        },
        {
            "id": "nhtsa_honda_tech_line",
            "source_class": "government_hosted_manufacturer",
            "url": "https://static.nhtsa.gov/odi/inv/2010/INRD-DP10004-48962P.pdf",
        },
        {
            "id": "edmunds_2009_civic_hybrid",
            "source_class": "vehicle_reference",
            "url": (
                "https://www.edmunds.com/honda/civic/2009/sedan/st-101061181/"
                "features-specs/"
            ),
        },
        {
            "id": "kbb_2009_civic_hybrid",
            "source_class": "vehicle_reference",
            "url": "https://www.kbb.com/honda/civic/2009/hybrid-sedan-4d/",
        },
        {
            "id": "cars_2009_civic_hybrid",
            "source_class": "vehicle_reference",
            "url": "https://www.cars.com/research/honda-civic_hybrid-2009/specs/",
        },
    ],
    "corroborated_groups": {
        "core_identity": {
            "match_count": 4,
            "sources": [
                "honda_2009_hybrid_fact_sheet",
                "edmunds_2009_civic_hybrid",
                "kbb_2009_civic_hybrid",
                "cars_2009_civic_hybrid",
            ],
        },
        "engine_performance": {
            "match_count": 4,
            "sources": [
                "honda_2009_hybrid_fact_sheet",
                "edmunds_2009_civic_hybrid",
                "kbb_2009_civic_hybrid",
                "cars_2009_civic_hybrid",
            ],
        },
        "fuel_efficiency": {
            "match_count": 4,
            "sources": [
                "honda_2009_hybrid_fact_sheet",
                "edmunds_2009_civic_hybrid",
                "kbb_2009_civic_hybrid",
                "cars_2009_civic_hybrid",
            ],
        },
        "dimensions_weight": {
            "match_count": 3,
            "sources": [
                "honda_2009_hybrid_fact_sheet",
                "edmunds_2009_civic_hybrid",
                "kbb_2009_civic_hybrid",
            ],
        },
        "interior": {
            "match_count": 3,
            "sources": [
                "honda_2009_hybrid_fact_sheet",
                "edmunds_2009_civic_hybrid",
                "kbb_2009_civic_hybrid",
            ],
        },
        "chassis": {
            "match_count": 3,
            "sources": [
                "honda_2009_hybrid_fact_sheet",
                "edmunds_2009_civic_hybrid",
                "cars_2009_civic_hybrid",
            ],
        },
    },
    "manufacturer_reported_groups": {
        "electrification_details": ["honda_2009_hybrid_fact_sheet"],
        "factory_feature_availability": ["honda_2009_hybrid_fact_sheet"],
        "service_specifications": ["honda_2009_hybrid_owner_manual"],
    },
    "preserved_conflicts": {
        "overall_length_in": {
            "selected_value": 177.3,
            "selected_reason": (
                "Honda fact sheet, Edmunds, and KBB agree on 177.3 in; Cars.com "
                "rounds this to 177 in."
            ),
            "conflicting_observation": {
                "value": 176.7,
                "source": "honda_2009_hybrid_owner_manual",
            },
        }
    },
}


def upgrade() -> None:
    op.create_table(
        "vehicle_specification_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_configuration_id", sa.Uuid(), nullable=False),
        sa.Column("profile_version", sa.SmallInteger(), nullable=False),
        sa.Column("verification_status", sa.String(length=32), nullable=False),
        sa.Column("source_match_count", sa.SmallInteger(), nullable=False),
        sa.Column("profile", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_matrix", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "profile_version >= 1",
            name="ck_vehicle_specification_profiles_version",
        ),
        sa.CheckConstraint(
            "source_match_count >= 1",
            name="ck_vehicle_specification_profiles_source_match_count",
        ),
        sa.CheckConstraint(
            "verification_status IN ('candidate', 'verified', 'superseded')",
            name="ck_vehicle_specification_profiles_status",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_configuration_id"],
            ["vehicle_configurations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "vehicle_configuration_id",
            name="uq_vehicle_specification_profiles_vehicle_configuration_id",
        ),
    )

    vehicle_configurations = sa.table(
        "vehicle_configurations",
        sa.column("id", sa.Uuid()),
        sa.column("identity_hash", sa.String()),
        sa.column("body_style", sa.String()),
        sa.column("engine", sa.String()),
        sa.column("drivetrain", sa.String()),
        sa.column("identity_source", sa.String()),
        sa.column("verification_status", sa.String()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        vehicle_configurations.update()
        .where(vehicle_configurations.c.id == VEHICLE_ID)
        .values(
            identity_hash=NEW_IDENTITY_HASH,
            body_style="Sedan",
            engine="1.3L I4 HYBRID",
            drivetrain="FWD",
            identity_source="multi_source",
            verification_status="verified",
            updated_at=sa.func.now(),
        )
    )

    profiles = sa.table(
        "vehicle_specification_profiles",
        sa.column("id", sa.Uuid()),
        sa.column("vehicle_configuration_id", sa.Uuid()),
        sa.column("profile_version", sa.SmallInteger()),
        sa.column("verification_status", sa.String()),
        sa.column("source_match_count", sa.SmallInteger()),
        sa.column("profile", postgresql.JSONB()),
        sa.column("source_matrix", postgresql.JSONB()),
    )
    op.bulk_insert(
        profiles,
        [
            {
                "id": PROFILE_ID,
                "vehicle_configuration_id": VEHICLE_ID,
                "profile_version": 1,
                "verification_status": "verified",
                "source_match_count": 4,
                "profile": PROFILE,
                "source_matrix": SOURCE_MATRIX,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("vehicle_specification_profiles")

    vehicle_configurations = sa.table(
        "vehicle_configurations",
        sa.column("id", sa.Uuid()),
        sa.column("identity_hash", sa.String()),
        sa.column("body_style", sa.String()),
        sa.column("engine", sa.String()),
        sa.column("drivetrain", sa.String()),
        sa.column("identity_source", sa.String()),
        sa.column("verification_status", sa.String()),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        vehicle_configurations.update()
        .where(vehicle_configurations.c.id == VEHICLE_ID)
        .values(
            identity_hash=OLD_IDENTITY_HASH,
            body_style=None,
            engine="I4 HYBRID",
            drivetrain=None,
            identity_source="nhtsa",
            verification_status="verified",
            updated_at=sa.func.now(),
        )
    )
