import unittest
from uuid import uuid4

from fastapi import status

from partgraph.errors import ErrorCode, PartGraphError
from partgraph.identity.auth.models import User
from partgraph.identity.auth.roles import (
    CONTRIBUTION_ROLES,
    CURATION_PUBLISH_ROLES,
    REVIEW_ROLES,
    require_any_role,
    require_role,
)

HUMAN_ROLES = (
    "owner",
    "contributor",
    "reviewer",
    "curator",
    "operator_admin",
)

EXPECTED_ALLOWED = {
    "contribution": frozenset({"contributor", "reviewer", "curator", "operator_admin"}),
    "review": frozenset({"reviewer", "curator", "operator_admin"}),
    "curation_publish": frozenset({"curator", "operator_admin"}),
    "operator": frozenset({"operator_admin"}),
}


def _user(role: str) -> User:
    suffix = uuid4().hex[:12]
    return User(
        id=uuid4(),
        email=f"rbac-{role}-{suffix}@example.invalid",
        username=f"rbac_{suffix}",
        password_hash="phase9-rbac-fixture",
        role=role,
        is_active=True,
    )


class FinalMvpHumanRbacTests(unittest.IsolatedAsyncioTestCase):
    def test_declared_role_sets_match_blueprint_hierarchy(self) -> None:
        self.assertEqual(CONTRIBUTION_ROLES, EXPECTED_ALLOWED["contribution"])
        self.assertEqual(REVIEW_ROLES, EXPECTED_ALLOWED["review"])
        self.assertEqual(CURATION_PUBLISH_ROLES, EXPECTED_ALLOWED["curation_publish"])

    async def _assert_role_gate(
        self,
        *,
        allowed: frozenset[str],
        dependency,
    ) -> None:
        for role in HUMAN_ROLES:
            user = _user(role)
            with self.subTest(role=role, allowed=role in allowed):
                if role in allowed:
                    self.assertIs(await dependency(user), user)
                    continue

                with self.assertRaises(PartGraphError) as denied:
                    await dependency(user)
                self.assertEqual(denied.exception.code, ErrorCode.RBAC_ROLE_REQUIRED)
                self.assertEqual(
                    denied.exception.status_code,
                    status.HTTP_403_FORBIDDEN,
                )
                self.assertFalse(denied.exception.retryable)
                self.assertEqual(
                    denied.exception.details,
                    {"allowed_roles": sorted(allowed)},
                )

    async def test_contribution_gate_allows_contributor_and_higher_roles(self) -> None:
        await self._assert_role_gate(
            allowed=EXPECTED_ALLOWED["contribution"],
            dependency=require_any_role(*sorted(CONTRIBUTION_ROLES)),
        )

    async def test_review_gate_excludes_owner_and_contributor(self) -> None:
        await self._assert_role_gate(
            allowed=EXPECTED_ALLOWED["review"],
            dependency=require_any_role(*sorted(REVIEW_ROLES)),
        )

    async def test_curation_publish_gate_requires_curator_or_operator(self) -> None:
        await self._assert_role_gate(
            allowed=EXPECTED_ALLOWED["curation_publish"],
            dependency=require_any_role(*sorted(CURATION_PUBLISH_ROLES)),
        )

    async def test_operator_gate_is_operator_admin_only(self) -> None:
        await self._assert_role_gate(
            allowed=EXPECTED_ALLOWED["operator"],
            dependency=require_role("operator_admin"),
        )

    def test_empty_role_gate_is_rejected_at_definition_time(self) -> None:
        with self.assertRaisesRegex(ValueError, "At least one role is required"):
            require_any_role()


if __name__ == "__main__":
    unittest.main()
