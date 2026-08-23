# PartGraph catalog ingestion

This folder is the boundary between **public catalog facts** and PartGraph's verified repair graph.

## What this pipeline may collect

- Honda OEM part number as printed on a public catalog page
- part name/description as printed by that source
- stated quantity when the page exposes one
- exact source URL
- source type/domain
- vehicle configuration selected by the source page
- a small text evidence window used for human review

The generated output is always `candidate` data.

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

## Running the collector

Node 18+ is required because the script uses the built-in `fetch` API.

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

The collector:

1. reads the explicit allow-list in `tools/catalog/sources.json`
2. checks `robots.txt`
3. fetches sequentially with a delay
4. extracts Honda-style OEM identifiers and nearby factual text
5. stores no raw HTML
6. downloads no images
7. writes candidates for review rather than editing the production graph

## Rights / terms boundary

`robots.txt` is only an automation signal; it is not a license. Every source has a `rightsStatus` field and still needs terms/licensing review before large-scale or commercial ingestion. Public factual identifiers can be useful evidence without copying a site's diagrams, prose, or image library.

Prefer, in order:

1. official Honda data / licensed Honda service and parts data
2. government/public vehicle metadata
3. authorized APIs or licensed structured catalog feeds
4. dealer/catalog pages as corroborating factual observations
5. marketplaces only for shopping after identity is established

## Database

`catalog/schema.sql` is deliberately SQLite/Cloudflare-D1 compatible. The current GitHub Pages app can continue reading its curated static graph while this ingestion layer matures. Later we can load reviewed catalog observations into D1 without changing the trust boundary.

The key separation is:

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

A scraper finding a part number is not permission to publish repair advice.
