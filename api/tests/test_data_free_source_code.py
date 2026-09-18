from __future__ import annotations

import json
import re
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = REPO_ROOT / "api" / "data" / "reference"
LEGACY_BOUNDARY_PATH = REFERENCE_ROOT / "legacy_migration_data_boundary_v1.json"

SCAN_ROOTS = (
    REPO_ROOT / "api" / "partgraph",
    REPO_ROOT / "api" / "tests",
    REPO_ROOT / "api" / "scripts",
    REPO_ROOT / "api" / "migrations" / "versions",
    REPO_ROOT / "web" / "src",
    REPO_ROOT / "web" / "scripts",
    REPO_ROOT / ".github" / "workflows",
)
SOURCE_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".yaml",
    ".yml",
    ".sh",
    ".sql",
}

VEHICLE_FACT_KEYS = {
    "year",
    "make",
    "model",
    "trim",
    "engine",
    "transmission",
    "drivetrain",
    "body_style",
}
EXACT_FACT_KEYS = {
    "vehicle_configuration_id",
    "document_part_number",
    "oem_part_number",
    "part_number",
    "instruction",
    "warning_text",
    "url",
}


@dataclass(frozen=True, slots=True)
class ReferenceFact:
    value: str
    source: str


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _legacy_migration_paths() -> set[Path]:
    payload = _load_json(LEGACY_BOUNDARY_PATH)
    return {
        (REPO_ROOT / "api" / "migrations" / "versions" / item["migration"]).resolve()
        for item in payload["legacy_revisions"]
    }


def _walk_reference_facts(value: Any, *, source: str, facts: set[ReferenceFact]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in VEHICLE_FACT_KEYS and item not in (None, ""):
                facts.add(ReferenceFact(str(item), f"{source}:{key}"))
            elif key in EXACT_FACT_KEYS and isinstance(item, (str, int, float)) and item != "":
                facts.add(ReferenceFact(str(item), f"{source}:{key}"))

            if key in {"display_name", "label", "title"} and isinstance(item, str):
                # Distinctive physical facts frequently encode size, grade, bulb type,
                # capacity, or other reference-specific values directly in the label.
                if any(char.isdigit() for char in item):
                    facts.add(ReferenceFact(item, f"{source}:{key}"))

            _walk_reference_facts(item, source=source, facts=facts)

        quantity = value.get("quantity")
        unit = value.get("unit")
        if (
            isinstance(quantity, (int, float))
            and quantity not in {0, 1}
            and isinstance(unit, str)
            and unit.strip()
            and unit.strip().casefold() != "each"
        ):
            facts.add(ReferenceFact(f"{quantity:g} {unit.strip()}", f"{source}:quantity+unit"))

        numeric_value = value.get("value")
        numeric_unit = value.get("unit")
        if (
            isinstance(numeric_value, (int, float))
            and isinstance(numeric_unit, str)
            and numeric_unit.strip()
        ):
            facts.add(
                ReferenceFact(
                    f"{numeric_value:g} {numeric_unit.strip()}",
                    f"{source}:value+unit",
                )
            )
        return

    if isinstance(value, list):
        for item in value:
            _walk_reference_facts(item, source=source, facts=facts)


def _reference_facts() -> set[ReferenceFact]:
    facts: set[ReferenceFact] = set()
    for path in sorted(REFERENCE_ROOT.rglob("*.json")):
        relative = path.relative_to(REPO_ROOT).as_posix()
        try:
            payload = _load_json(path)
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        _walk_reference_facts(payload, source=relative, facts=facts)

    # Short/generic values are too collision-prone to be useful as source guards.
    return {
        fact
        for fact in facts
        if len(fact.value.strip()) >= 3
        and fact.value.strip().casefold() not in {"sedan", "cvt", "fwd", "awd", "us"}
    }


def _source_paths() -> list[Path]:
    legacy_migrations = _legacy_migration_paths()
    paths: list[Path] = []
    for root in SCAN_ROOTS:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
                continue
            if path.resolve() in legacy_migrations:
                continue
            paths.append(path)
    return sorted(paths)


def _contains_fact(source: str, fact: str) -> bool:
    if fact.isdigit():
        return re.search(rf"(?<!\d){re.escape(fact)}(?!\d)", source) is not None
    return fact.casefold() in source.casefold()


class DataFreeSourceCodeTests(unittest.TestCase):
    def test_reference_automotive_facts_are_not_embedded_in_executable_source(self) -> None:
        facts = sorted(_reference_facts(), key=lambda item: (-len(item.value), item.value))
        self.assertTrue(facts)

        violations: list[str] = []
        this_file = Path(__file__).resolve()
        for path in _source_paths():
            if path.resolve() == this_file:
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for fact in facts:
                if _contains_fact(source, fact.value):
                    relative = path.relative_to(REPO_ROOT).as_posix()
                    violations.append(
                        f"{relative} embeds {fact.value!r} from {fact.source}"
                    )

        self.assertFalse(
            violations,
            "Reference automotive facts must live in data, not executable source:\n"
            + "\n".join(sorted(set(violations))),
        )


if __name__ == "__main__":
    unittest.main()
