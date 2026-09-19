from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PARTGRAPH_ROOT = REPO_ROOT / "api" / "partgraph"
RETIRED_PACKAGES = (
    PARTGRAPH_ROOT / "auth",
    PARTGRAPH_ROOT / "user_vehicle",
    PARTGRAPH_ROOT / "repair_definition",
    PARTGRAPH_ROOT / "repair_experience" / "repair_session",
)
RETIRED_IMPORT_PATTERNS = (
    re.compile(r"\b(?:from|import)\s+partgraph\.auth\b"),
    re.compile(r"\b(?:from|import)\s+partgraph\.user_vehicle\b"),
    re.compile(r"\b(?:from|import)\s+partgraph\.repair_definition\b"),
    re.compile(r"\b(?:from|import)\s+partgraph\.repair_experience\.repair_session\b"),
)


class RetiredCompatibilityBridgeTests(unittest.TestCase):
    def test_legacy_bridge_packages_stay_removed(self) -> None:
        for package_path in RETIRED_PACKAGES:
            with self.subTest(package_path=package_path.relative_to(REPO_ROOT)):
                self.assertFalse(
                    package_path.exists(),
                    f"retired compatibility package returned: {package_path.relative_to(REPO_ROOT)}",
                )

    def test_executable_python_uses_canonical_import_paths(self) -> None:
        offenders: list[str] = []
        own_path = Path(__file__).resolve()

        for path in (REPO_ROOT / "api").rglob("*.py"):
            if path.resolve() == own_path:
                continue
            text = path.read_text(encoding="utf-8")
            if any(pattern.search(text) for pattern in RETIRED_IMPORT_PATTERNS):
                offenders.append(str(path.relative_to(REPO_ROOT)))

        self.assertEqual(
            offenders,
            [],
            "retired compatibility imports remain: " + ", ".join(sorted(offenders)),
        )


if __name__ == "__main__":
    unittest.main()
