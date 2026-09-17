import os
import unittest
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

import partgraph.orm_registry  # noqa: F401
from partgraph.database import Base

DATABASE_URL_ENV = "PARTGRAPH_DATABASE_URL"
API_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config() -> Config:
    return Config(str(API_ROOT / "alembic.ini"))


def _script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(_alembic_config())


class FinalMvpMigrationTests(unittest.TestCase):
    def test_revision_graph_has_one_linear_head_and_one_base(self) -> None:
        script = _script_directory()
        heads = script.get_heads()
        self.assertEqual(len(heads), 1, heads)

        revisions = list(script.walk_revisions())
        self.assertGreater(len(revisions), 0)
        self.assertEqual(len({revision.revision for revision in revisions}), len(revisions))

        bases = []
        for revision in revisions:
            down_revision = revision.down_revision
            if down_revision is None:
                bases.append(revision.revision)
                continue
            self.assertIsInstance(
                down_revision,
                str,
                f"merge/branch revision is not allowed in final MVP history: {revision.revision}",
            )

        self.assertEqual(len(bases), 1, bases)

    def test_every_parent_revision_is_present(self) -> None:
        revisions = list(_script_directory().walk_revisions())
        revision_ids = {revision.revision for revision in revisions}

        for revision in revisions:
            if revision.down_revision is not None:
                self.assertIn(
                    revision.down_revision,
                    revision_ids,
                    f"missing parent for revision {revision.revision}",
                )

    @unittest.skipUnless(
        os.getenv(DATABASE_URL_ENV),
        f"{DATABASE_URL_ENV} is required for migrated-database contracts",
    )
    def test_fresh_database_is_stamped_at_exact_head(self) -> None:
        script = _script_directory()
        expected_head = script.get_current_head()
        self.assertIsNotNone(expected_head)

        engine = create_engine(os.environ[DATABASE_URL_ENV])
        try:
            with engine.connect() as connection:
                actual_head = connection.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                ).scalar_one()
        finally:
            engine.dispose()

        self.assertEqual(actual_head, expected_head)

    @unittest.skipUnless(
        os.getenv(DATABASE_URL_ENV),
        f"{DATABASE_URL_ENV} is required for migrated-database contracts",
    )
    def test_fresh_database_contains_every_registered_orm_table_and_column(self) -> None:
        engine = create_engine(os.environ[DATABASE_URL_ENV])
        try:
            database = inspect(engine)
            for table in Base.metadata.sorted_tables:
                with self.subTest(table=table.fullname):
                    self.assertTrue(
                        database.has_table(table.name, schema=table.schema),
                        f"missing migrated table {table.fullname}",
                    )
                    migrated_columns = {
                        column["name"]
                        for column in database.get_columns(
                            table.name,
                            schema=table.schema,
                        )
                    }
                    orm_columns = {column.name for column in table.columns}
                    self.assertEqual(
                        orm_columns - migrated_columns,
                        set(),
                        f"migration is missing ORM columns for {table.fullname}",
                    )
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
