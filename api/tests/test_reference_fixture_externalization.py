import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BOUNDARY_PATH = REPO_ROOT / "api/data/reference/legacy_migration_data_boundary_v1.json"
MIGRATIONS_DIR = REPO_ROOT / "api/migrations/versions"


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


if __name__ == "__main__":
    unittest.main()
