# PartGraph Engineering Authority

Canonical architecture: `docs/BLUEPRINT.md`  
Implementation sequence/status: `docs/ROADMAP.md`  
Deferred audit/governance register: `docs/AUDIT_STATUS.md`

Do not treat historical branch notes, superseded audit narratives, old UMLs, old collector rules, old README content, or archived datasets as architecture instructions.

Core invariant: application source code processes generic schemas and stored data. Real vehicle year/make/model/trim identities and vehicle-specific mechanical facts belong in databases or approved data/fixture files, not application/test/CI logic.

When implementation evidence conflicts with documentation, verify the current code/database behavior and update the canonical Blueprint/Roadmap deliberately rather than silently changing architecture.
