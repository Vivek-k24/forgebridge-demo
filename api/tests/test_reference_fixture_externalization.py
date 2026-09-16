import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BOUNDARY_PATH = REPO_ROOT / "api/data/reference/legacy_migration_data_boundary_v1.json"
MIGRATIONS_DIR = REPO_ROOT / "api/migrations/versions"
WORKBOOK_NAME = "Selected_Asian_Brands_1996_2000.xlsx"
API_WORKBOOK = REPO_ROOT / "api/data" / WORKBOOK_NAME
DOCS_WORKBOOK = REPO_ROOT / "docs" / WORKBOOK_NAME
LEGACY_ARCHIVE_DIR = REPO_ROOT / "api/data/archive/reference_fleet_legacy"
LEGACY_ARCHIVE_TOKENS = {
    "reference-fleet-v1.json",
    "repair-corpus-v1.json",
    "reference_fleet_legacy",
}
EXECUTABLE_SUFFIXES = {".js", ".jsx", ".py", ".sh", ".toml", ".ts", ".tsx", ".yaml", ".yml"}


class ReferenceFixtureExternalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.boundary = json.loads(BOUNDARY_PATH.read_text(encoding="utf-8"))

    def test_every_legacy_data_migration_has_externalized_data(self) -> None:
        revisions = self.boundary["legacy_revisions"]
        self.assertTrue(revisions)
        for item in revisions:
            migration = MIGRATIONS_DIR / item["migration"]
            self.assertTrue(migration.is_file(), migration)
            paths = item["externalized_paths"]
            self.assertTrue(paths, item["migration"])
            for relative_path in paths:
                path = REPO_ROOT / relative_path
                self.assertTrue(path.is_file(), path)
                if path.suffix == ".json":
                    json.loads(path.read_text(encoding="utf-8"))

    def test_future_migrations_do_not_reimport_externalized_legacy_artifacts(self) -> None:
        revisions = self.boundary["legacy_revisions"]
        legacy_migrations = {item["migration"] for item in revisions}
        artifact_names = {
            Path(path).name
            for item in revisions
            for path in item["externalized_paths"]
        }

        for migration in sorted(MIGRATIONS_DIR.glob("*.py")):
            if migration.name in legacy_migrations:
                continue
            prefix = migration.name.split("_", 1)[0]
            if not prefix.isdigit() or int(prefix) <= 20:
                continue
            source = migration.read_text(encoding="utf-8")
            for artifact_name in artifact_names:
                self.assertNotIn(
                    artifact_name,
                    source,
                    f"{migration.name} reimports legacy reference artifact {artifact_name}",
                )

    def test_externalized_profile_manifest_resolves_all_declared_files(self) -> None:
        manifests = sorted((REPO_ROOT / "api/data/reference").glob("*/manifest.json"))
        self.assertTrue(manifests)
        for manifest_path in manifests:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            declared_files = manifest.get("files", {})
            for relative_name in declared_files.values():
                fixture_path = manifest_path.parent / relative_name
                self.assertTrue(fixture_path.is_file(), fixture_path)
                json.loads(fixture_path.read_text(encoding="utf-8"))

    def test_legacy_workbook_has_one_documented_working_tree_copy(self) -> None:
        copies = sorted(REPO_ROOT.rglob(WORKBOOK_NAME))
        self.assertEqual(copies, [API_WORKBOOK])
        self.assertTrue(API_WORKBOOK.is_file())
        self.assertFalse(DOCS_WORKBOOK.exists())

        externalized_paths = {
            path
            for item in self.boundary["legacy_revisions"]
            for path in item["externalized_paths"]
        }
        self.assertIn(f"api/data/{WORKBOOK_NAME}", externalized_paths)

        migration = (MIGRATIONS_DIR / "0017_selected_asian_workbook.py").read_text(encoding="utf-8")
        self.assertIn(f'WORKBOOK_NAME = "{WORKBOOK_NAME}"', migration)
        self.assertIn('WORKBOOK_PATH = Path(__file__).resolve().parents[2] / "data" / WORKBOOK_NAME', migration)

    def test_removed_legacy_archive_has_no_executable_dependency(self) -> None:
        self.assertFalse(LEGACY_ARCHIVE_DIR.exists())
        roots = (REPO_ROOT / "api", REPO_ROOT / ".github/workflows", REPO_ROOT / "web/src")
        this_file = Path(__file__).resolve()

        for root in roots:
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.resolve() == this_file:
                    continue
                if path.suffix not in EXECUTABLE_SUFFIXES:
                    continue
                try:
                    source = path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                for token in LEGACY_ARCHIVE_TOKENS:
                    self.assertNotIn(token, source, f"{path} still depends on removed legacy archive {token}")


if __name__ == "__main__":
    unittest.main()
