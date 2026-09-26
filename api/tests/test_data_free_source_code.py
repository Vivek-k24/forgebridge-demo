from __future__ import annotations

import json
import re
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOTS = (
    REPO_ROOT / "api" / "data" / "reference",
    REPO_ROOT / "api" / "data" / "reference_candidates",
)

SCAN_ROOTS = (
    REPO_ROOT / "api" / "partgraph",
    REPO_ROOT / "api" / "tests",
    REPO_ROOT / "api" / "scripts",
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

IDENTITY_FACT_KEYS = {
    "year",
    "make",
    "model",
    "trim",
}
STRONG_FACT_KEYS = {
    "vehicle_configuration_id",
    "engine",
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
    category: str


@dataclass(frozen=True, slots=True)
class ReferenceIdentity:
    source: str
    facts: tuple[ReferenceFact, ...]


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _fact(value: object, *, source: str, category: str) -> ReferenceFact | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip()
    if len(normalized) < 3:
        return None
    return ReferenceFact(normalized, source, category)


def _walk_reference_data(
    value: Any,
    *,
    source: str,
    strong_facts: set[ReferenceFact],
    identities: set[ReferenceIdentity],
) -> None:
    if isinstance(value, dict):
        identity_items: list[ReferenceFact] = []
        for key in IDENTITY_FACT_KEYS:
            if key in value:
                item = _fact(value[key], source=f"{source}:{key}", category=key)
                if item is not None:
                    identity_items.append(item)
        if len(identity_items) >= 2:
            identities.add(
                ReferenceIdentity(
                    source=source,
                    facts=tuple(sorted(identity_items, key=lambda item: item.category)),
                )
            )

        for key, item in value.items():
            if key in STRONG_FACT_KEYS and isinstance(item, (str, int, float)):
                fact = _fact(item, source=f"{source}:{key}", category=key)
                if fact is not None:
                    strong_facts.add(fact)

            if key in {"display_name", "label", "title"} and isinstance(item, str):
                if any(char.isdigit() for char in item):
                    fact = _fact(item, source=f"{source}:{key}", category=key)
                    if fact is not None:
                        strong_facts.add(fact)

            _walk_reference_data(
                item,
                source=source,
                strong_facts=strong_facts,
                identities=identities,
            )

        quantity = value.get("quantity")
        unit = value.get("unit")
        if (
            isinstance(quantity, (int, float))
            and quantity not in {0, 1}
            and isinstance(unit, str)
            and unit.strip()
            and unit.strip().casefold() != "each"
        ):
            strong_facts.add(
                ReferenceFact(
                    f"{quantity:g} {unit.strip()}",
                    f"{source}:quantity+unit",
                    "quantity+unit",
                )
            )

        numeric_value = value.get("value")
        numeric_unit = value.get("unit")
        if (
            isinstance(numeric_value, (int, float))
            and isinstance(numeric_unit, str)
            and numeric_unit.strip()
        ):
            strong_facts.add(
                ReferenceFact(
                    f"{numeric_value:g} {numeric_unit.strip()}",
                    f"{source}:value+unit",
                    "value+unit",
                )
            )
        return

    if isinstance(value, list):
        for item in value:
            _walk_reference_data(
                item,
                source=source,
                strong_facts=strong_facts,
                identities=identities,
            )


def _reference_contract() -> tuple[set[ReferenceFact], set[ReferenceIdentity]]:
    strong_facts: set[ReferenceFact] = set()
    identities: set[ReferenceIdentity] = set()
    for root in REFERENCE_ROOTS:
        for path in sorted(root.rglob("*.json")):
            relative = path.relative_to(REPO_ROOT).as_posix()
            try:
                payload = _load_json(path)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            _walk_reference_data(
                payload,
                source=relative,
                strong_facts=strong_facts,
                identities=identities,
            )
    return strong_facts, identities


def _source_paths() -> list[Path]:
    paths: list[Path] = []
    for root in SCAN_ROOTS:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES:
                paths.append(path)
    return sorted(paths)


def _contains_fact(source: str, fact: str) -> bool:
    if fact.isdigit():
        return re.search(rf"(?<!\d){re.escape(fact)}(?!\d)", source) is not None
    return fact.casefold() in source.casefold()


class DataFreeSourceCodeTests(unittest.TestCase):
    def test_reference_automotive_facts_are_not_embedded_in_executable_source(self) -> None:
        strong_facts, identities = _reference_contract()
        self.assertTrue(strong_facts)
        self.assertTrue(identities)

        violations: list[str] = []
        this_file = Path(__file__).resolve()
        for path in _source_paths():
            if path.resolve() == this_file:
                continue
            try:
                source = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            relative = path.relative_to(REPO_ROOT).as_posix()

            for fact in strong_facts:
                if _contains_fact(source, fact.value):
                    violations.append(
                        f"{relative} embeds strong reference fact {fact.value!r} "
                        f"from {fact.source}"
                    )

            for identity in identities:
                matched = {
                    fact.category: fact.value
                    for fact in identity.facts
                    if _contains_fact(source, fact.value)
                }
                if len(matched) >= 2:
                    detail = ", ".join(
                        f"{category}={value!r}"
                        for category, value in sorted(matched.items())
                    )
                    violations.append(
                        f"{relative} embeds reference identity combination "
                        f"from {identity.source}: {detail}"
                    )

        self.assertFalse(
            violations,
            "Reference automotive facts must live in data, not executable source:\n"
            + "\n".join(sorted(set(violations))),
        )


if __name__ == "__main__":
    unittest.main()
