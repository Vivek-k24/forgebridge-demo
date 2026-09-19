from __future__ import annotations

import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "api"
PARTGRAPH_ROOT = API_ROOT / "partgraph"
RETIRED_MODULES = (
    "partgraph.auth",
    "partgraph.user_vehicle",
    "partgraph.repair_definition",
    "partgraph.repair_experience.repair_session",
)
RETIRED_PACKAGES = (
    PARTGRAPH_ROOT / "auth",
    PARTGRAPH_ROOT / "user_vehicle",
    PARTGRAPH_ROOT / "repair_definition",
    PARTGRAPH_ROOT / "repair_experience" / "repair_session",
)


def _module_name(path: Path) -> tuple[list[str], bool]:
    relative = path.relative_to(API_ROOT)
    parts = list(relative.with_suffix("").parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]
    return parts, is_package


def _resolved_import(path: Path, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""

    module_parts, is_package = _module_name(path)
    package_parts = module_parts if is_package else module_parts[:-1]
    ascend = node.level - 1
    if ascend > len(package_parts):
        return ""

    base = package_parts[: len(package_parts) - ascend]
    if node.module:
        base.extend(node.module.split("."))
    return ".".join(base)


def _is_retired(module_name: str) -> bool:
    return any(
        module_name == retired or module_name.startswith(f"{retired}.")
        for retired in RETIRED_MODULES
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

        for path in API_ROOT.rglob("*.py"):
            if path.resolve() == own_path:
                continue

            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                imported: list[str] = []
                if isinstance(node, ast.Import):
                    imported.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imported.append(_resolved_import(path, node))

                for module_name in imported:
                    if _is_retired(module_name):
                        offenders.append(
                            f"{path.relative_to(REPO_ROOT)}:{node.lineno}:{module_name}"
                        )

        self.assertEqual(
            offenders,
            [],
            "retired compatibility imports remain: " + ", ".join(sorted(offenders)),
        )


if __name__ == "__main__":
    unittest.main()
