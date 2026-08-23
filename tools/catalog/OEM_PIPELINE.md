# Honda OEM ingestion pipeline

PartGraph must not invent vehicle coverage. The consumer UI reads only **published repair coverage**; broad Honda discovery and catalog acquisition happen offline.

## Authoritative source

For U.S. Honda vehicles, American Honda ServiceExpress is the OEM authority used by this pipeline. Honda's own ServiceExpress guide documents a Parts Info catalog that is searched by VIN and then browsed by section/illustration.

- ServiceExpress: https://techinfo.honda.com/rjanisis/logon.aspx
- Honda independent repair guide: https://techinfo.honda.com/rjanisis/pubs/Web/SvcExp_QS.pdf

ServiceExpress is authenticated/subscription content. The repository does **not** contain credentials and the tooling does not bypass authentication. Obtain data under the applicable Honda terms, save/export the relevant Parts Info result, then import it locally.

## Pipeline

```text
Honda ServiceExpress Parts Info
        ↓ legitimate operator access
saved JSON / text / HTML snapshot
        ↓
import-honda-service-express.mjs
        ↓
OEM candidate (part number/name/qty/callout only)
        ↓
review-honda-oem-candidate.mjs
        ↓ explicit human approval
reviewed OEM identity/fitment evidence
        ↓
mechanical graph authoring + separate service sources
        ↓
validation tests
        ↓
published Honda coverage registry
        ↓
consumer Step 1 → Step 2
```

The current public build exposes only configurations present in `src/data/hondaPublishedCoverage.ts`. That prevents the previous dead-end where the UI identified a Honda for which no reviewed repair graph existed.

## Import

```bash
node tools/catalog/import-honda-service-express.mjs \
  --input ./private/radiator.html \
  --vehicle honda-civic-2009-hybrid-us \
  --section radiator-denso \
  --source-url "<the ServiceExpress Parts Info URL used for the capture>"
```

The importer uses deterministic text/JSON parsing and **zero LLM tokens**. It hashes the source snapshot and emits only candidate facts.

## Review

```bash
node tools/catalog/review-honda-oem-candidate.mjs \
  --input catalog/generated/honda-civic-2009-hybrid-us.radiator-denso.oem-candidate.json \
  --reviewer "initials-or-name" \
  --decision approve
```

Approval means only:

- this OEM part number/name/quantity was reviewed against the captured Honda Parts Info source;
- it belongs to the stated vehicle configuration/section.

Approval does **not** mean:

- torque is known;
- the part must always be replaced;
- a fastener is single-use;
- a fluid, pressure, refrigerant quantity or service procedure is known;
- an aftermarket interchange is safe;
- a mechanical relationship has been proven.

Those are separate claims and need their own authoritative source/provenance.

## Public corroboration collector

`npm run catalog:scrape` remains useful for public dealer/catalog pages, but those observations are corroboration/candidates only. They cannot promote themselves into OEM truth.

## Scaling Honda coverage

For each new vehicle configuration:

1. resolve the exact Honda catalog configuration/VIN applicability;
2. capture the relevant OEM sections;
3. import and review part identity/fitment;
4. author typed mechanical relationships from authoritative service/engineering evidence;
5. run graph invariants/golden repair tests;
6. add the configuration to `hondaPublishedCoverage.ts` only after the graph is ready.

This is intentionally slower than guessing. A PartGraph user should never be allowed to enter a repair workflow that silently substitutes another trim's graph.
