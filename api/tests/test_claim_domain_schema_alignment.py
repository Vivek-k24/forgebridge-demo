import ast
import re
import unittest
from pathlib import Path

from sqlalchemy import CheckConstraint

from partgraph.knowledge.models import MechanicalClaim
from partgraph.knowledge.provenance import CLAIM_DOMAINS, SourceAuthorityPolicy
from partgraph.knowledge.source_policy import ClaimDomain


class ClaimDomainSchemaAlignmentTests(unittest.TestCase):
    @staticmethod
    def _constraint_values(table: object, constraint_name: str) -> set[str]:
        constraints = [
            constraint
            for constraint in table.constraints  # type: ignore[attr-defined]
            if isinstance(constraint, CheckConstraint) and constraint.name == constraint_name
        ]
        if len(constraints) != 1:
            raise AssertionError(
                f"expected exactly one {constraint_name!r} constraint, found {len(constraints)}"
            )
        return set(re.findall(r"'([^']+)'", str(constraints[0].sqltext)))

    @staticmethod
    def _migration_tuple(name: str) -> tuple[str, ...]:
        migration_path = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "versions"
            / "0059_primary_vehicle_domains.py"
        )
        tree = ast.parse(migration_path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                value = ast.literal_eval(node.value)
                if not isinstance(value, tuple) or not all(
                    isinstance(item, str) for item in value
                ):
                    raise AssertionError(f"{name} is not a tuple[str, ...]")
                return value
        raise AssertionError(f"could not find {name} in migration 0059")

    def test_claim_domains_match_policy_migration_and_orm_constraints(self) -> None:
        policy_domains = {domain.value for domain in ClaimDomain}
        migration_domains = set(self._migration_tuple("OLD_CLAIM_DOMAINS")) | set(
            self._migration_tuple("NEW_CLAIM_DOMAINS")
        )
        provenance_domains = set(CLAIM_DOMAINS)
        mechanical_claim_domains = self._constraint_values(
            MechanicalClaim.__table__, "ck_mechanical_claims_domain"
        )
        authority_policy_domains = self._constraint_values(
            SourceAuthorityPolicy.__table__,
            "ck_source_authority_policies_claim_domain",
        )

        self.assertEqual(policy_domains, migration_domains)
        self.assertEqual(policy_domains, provenance_domains)
        self.assertEqual(policy_domains, mechanical_claim_domains)
        self.assertEqual(policy_domains, authority_policy_domains)

        self.assertIn(ClaimDomain.VEHICLE_STRUCTURE.value, mechanical_claim_domains)
        self.assertIn(ClaimDomain.VEHICLE_SPECIFICATION.value, mechanical_claim_domains)


if __name__ == "__main__":
    unittest.main()
