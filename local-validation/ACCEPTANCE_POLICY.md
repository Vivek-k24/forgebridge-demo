# Standing local acceptance policy

For every new user-facing PartGraph workflow after this block:

1. preserve normal deterministic unit/integration/security tests in the existing engineering test suite;
2. add or extend a **local-only** acceptance scenario under `local-validation/`;
3. give the workflow an explicit observable contract (response, persistent state, rejection, event, projection, or reconstruction result);
4. exercise that contract through public APIs wherever practical;
5. use direct database fixture setup only to establish test preconditions that production would normally obtain from verified source ingestion;
6. keep all synthetic mechanical facts visibly test-only and isolated from normal PartGraph data;
7. use a reproducible seed when randomizing vehicles/scenarios;
8. never report a workflow as covered unless its assertion actually executed;
9. keep this acceptance harness out of CI/CD and deployment unless an explicit future decision changes that policy;
10. require a local PASS report before treating a materially new workflow as locally acceptance-verified.

This harness complements, rather than replaces, normal automated tests and human UI black-box testing.
