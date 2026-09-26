# PartGraph GitHub Branch Protection Runbook

Status: **active governance control; `PG-AUD-DEP-003` closed on 2026-09-20.** This document does not authorize PR #84 merge or any Production deployment/database change.

Machine-readable policy: `ops/cutover/phase10_branch_governance_v1.json`

## Current state

As of 2026-09-20:

- repository: `Vivek-k24/forgebridge-demo`;
- visibility: public;
- default branch: `main`;
- `main` reports `protected=true`;
- repository rulesets: none, consistent with the owner-applied classic branch-protection rule;
- the project owner reports applying the prepared policy in this runbook;
- the connected GitHub App still cannot read the detailed classic branch-protection endpoint because it lacks repository Administration permission.

The observable GitHub branch state plus the owner's application of the prepared policy closes the governance finding without attempting a destructive direct-push test.

## Prepared policy

Protect **`main` only**.

Configure:

- Require a pull request before merging: **on**.
- Required approving reviews: **0**.
- Require status checks before merging: **on**.
- Required check: **`MVP merge gate`**.
- Require branches to be up to date before merging: **on**.
- Require conversation resolution before merging: **on**.
- Allow force pushes: **off**.
- Allow deletions: **off**.
- Apply/enforce the rule for administrators where the selected GitHub protection surface supports it.
- Require signed commits: **off for the MVP**.
- Require linear history: **off for the MVP**.
- Lock branch: **off**.

Do not protect `partgraph-mvp-consolidation` or normal feature branches merely to close this audit item.

## Why zero required reviews

This repository is currently operated as a solo-owner project. GitHub does not allow the author to approve their own pull request. Requiring one approving review would therefore turn protection into a self-lockout rather than a safety control.

The safety objective is instead:

1. no direct release-branch changes;
2. every merge goes through a pull request;
3. the candidate must be current with `main`;
4. all 18 final-MVP validation jobs must pass through one stable aggregate check;
5. unresolved review conversations must be cleared;
6. destructive force-push/delete operations stay blocked.

If additional human maintainers/reviewers are added later, raise the approval count as a separate governance decision.

## MVP merge gate

`.github/workflows/mvp-validation.yml` runs for every pull request without path filtering.

Its `MVP merge gate` job depends on all 18 Phase 9 final-validation jobs. It fails if any dependency is not `success`, then validates this branch-governance contract.

This gives branch protection one stable required check and avoids requiring path-filtered API/Web/database workflows that may legitimately not run for a documentation-only pull request.

## Activation verification

The project owner applied the rule on 2026-09-20. The integration verified `main.protected=true` and zero repository rulesets. Because detailed classic branch-protection settings are not readable by the connected GitHub App, the remaining per-toggle evidence is the owner-applied prepared policy rather than API readback.

For future revalidation:

1. read `main` and confirm it reports protected;
2. confirm the rule/ruleset targets only `main`;
3. confirm `MVP merge gate` is the required status check;
4. confirm pull requests are required with zero approvals;
5. confirm branch-up-to-date and conversation-resolution requirements;
6. confirm force pushes and deletions are disabled;
7. create or use a harmless non-Production test PR and verify direct merge is unavailable until `MVP merge gate` succeeds;
8. record the rule/ruleset identifier and timestamp in the Phase 10 preflight.

Do not use PR #84 itself as the first destructive/governance experiment immediately before Production cutover.
