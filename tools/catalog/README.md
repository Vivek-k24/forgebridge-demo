# PartGraph catalog ingestion

This folder is the boundary between **catalog facts** and PartGraph's verified repair graph.

PartGraph now has two deterministic collectors:

1. `tools/catalog/scrape-public-catalog.mjs` — small explicit allow-list collector that writes JSON candidates.
2. `scripts/build_honda_parts_catalog.py` — exact-vehicle collector that discovers assembly pages and builds an appendable SQLite parts catalog.

Both use **zero LLM tokens**.

## What this pipeline may collect

- Honda-style OEM part number as printed on a catalog page
- part name/description as printed by that source
- stated quantity when the page exposes one
- exact source URL
- source type/domain and rights-review state
- exact vehicle configuration selected by the source page
- source assembly/category membership
- a small text evidence window used for human review
- a remote product-image reference when the same page exposes an image tied to the OEM number

The generated records remain `candidate` data until separately reviewed.

## What it must never infer

Catalog/seller pages are not a repair manual. Do not infer or publish from them alone:

- torque values
- fluid/refrigerant type or quantity
- pressure limits
- removal/install order
- metallurgy or material compatibility
- whether a fastener is single-use
- whether a seal must be replaced
- electrical test values
- hybrid/SRS/brake/refrigerant safety procedure
- part-to-part mechanical relationships that the source does not explicitly establish
- aftermarket interchange

Those belong in a separate mechanical/service story backed by manufacturer service information or another authoritative licensed source.

## Build a local Honda parts database

The parts database builder starts from the exact configuration catalog already generated in `public/data/honda/years/`.

Example: inspect the 2009 Civic configurations first, then choose one exact key.

```bash
python scripts/build_honda_parts_catalog.py \
  --year 2009 \
  --model Civic \
  --config-key "2009:civic:4dr_mx_hybrid:ka_cvt" \
  --assembly-contains radiator \
  --max-assemblies 5
```

Default output:

```text
data/catalog/honda-parts.sqlite
```

The database is appendable. Run the tool again for another exact configuration and it adds new vehicles, assemblies, part numbers and source observations without replacing reviewed data.

Useful modes:

```bash
# Discover/collect a small bounded set
python scripts/build_honda_parts_catalog.py --year 2009 --model Civic --configuration-contains "MX Hybrid" --max-assemblies 3

# Re-use locally cached pages; make no network requests
python scripts/build_honda_parts_catalog.py --year 2009 --model Civic --config-key "2009:civic:4dr_mx_hybrid:ka_cvt" --offline

# Ignore cache and re-fetch
python scripts/build_honda_parts_catalog.py --year 2009 --model Civic --config-key "2009:civic:4dr_mx_hybrid:ka_cvt" --refresh --max-assemblies 2

# Deterministic parser + SQLite persistence check; no network
npm run catalog:parts:self-test
```

### What the database contains

```text
vehicle_configs
      ↓
assemblies
      ↓
assembly_part_observations
      ↓
parts + part_fitment_observations
      ↓
source provenance / optional remote media reference
```

Assembly membership means only **“this source page listed this part inside this catalog assembly.”** It does not mean PartGraph has verified physical connection, removal order, or service dependency.

## Retrieval behavior

The Python collector:

1. loads one exact vehicle configuration from the generated Honda vehicle catalog
2. checks `robots.txt`
3. fetches the exact vehicle catalog page
4. discovers only same-host parts-list links for that exact configuration
5. applies an optional assembly filter and safety cap
6. fetches sequentially with a delay
7. extracts OEM-number/name/quantity observations
8. persists candidate observations and provenance into SQLite
9. caches fetched HTML under `.cache/partgraph/` so repeated development runs do not waste requests
10. continues across individual assembly failures unless `--fail-fast` is supplied

The cache and generated SQLite database are local development artifacts and are gitignored.

## Existing explicit-source collector

```bash
npm run catalog:scrape
```

Useful filters:

```bash
node tools/catalog/scrape-public-catalog.mjs --limit=2
node tools/catalog/scrape-public-catalog.mjs --domain=www.hondapartsnow.com
```

Output:

```text
data/catalog/part-candidates.json
```

That collector reads the explicit allow-list in `tools/catalog/sources.json`, checks `robots.txt`, stores no raw HTML, downloads no images, and writes candidates for review rather than editing the production graph.

## Rights / terms boundary

`robots.txt` is only an automation signal; it is not a license. Every source still needs terms/licensing review before large-scale or commercial ingestion. The parts builder's disk cache is for local development and should not be published or treated as a reusable copy of a third-party catalog.

Prefer, in order:

1. official Honda data / licensed Honda service and parts data
2. government/public vehicle metadata
3. authorized APIs or licensed structured catalog feeds
4. dealer/catalog pages as corroborating factual observations
5. marketplaces only for shopping after identity is established

## Database

`catalog/schema.sql` remains SQLite/Cloudflare-D1 compatible. It stores vehicle identity, part identity, fitment observations, catalog assembly membership, provenance and reference-only media URLs. The current GitHub Pages app can continue reading its curated static repair graph while this ingestion layer matures.

The trust path is:

```text
catalog observation
        ↓
human/source verification
        ↓
verified part identity + fitment
        ↓
mechanical/service verification (separate story)
        ↓
repair graph
```

A crawler finding a part number is not permission to publish repair advice.
