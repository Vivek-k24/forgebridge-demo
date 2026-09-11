# PartGraph catalog data acquisition

PartGraph should collect broadly and promote conservatively.

The existing `catalog_staging` schema is the ingestion lake boundary. It is
allowed to contain heterogeneous, incomplete, conflicting, and unstructured
observations as long as every observation preserves source provenance and the
original payload. Collectors do not write canonical mechanical truth.

## Trust layers

### Bronze: source observations

`catalog_staging.ingestion_batches` and `catalog_staging.source_records` are the
Bronze layer. Preserve the source response as `raw_payload`, its SHA-256,
source record identifier/URL, timestamps, collector version, extraction method,
and provenance. Do not discard fields merely because the current canonical
schema does not understand them.

Large binary documents should eventually be stored outside PostgreSQL with a
content-addressed URI and checksum; extracted text/metadata can remain in the
staging row. Raw binary blobs should not become canonical database columns.

### Silver: extracted candidates

`candidate_payload` is a schema-on-read extraction from the raw observation.
Candidate types currently include:

- `vehicle_trim_candidate`
- `part_candidate`
- `part_fitment_candidate`
- `inventory_offer_candidate`

Candidates may be normalized, clustered, linked, and deduplicated without
rewriting the raw source. Multiple conflicting candidates may coexist.

### Gold: canonical / verified data

Promotion into canonical vehicle identity, part identity, fitment, repair, or
verified-evidence structures requires source-policy checks and, where required,
human review. Parser/model confidence is not source authority.

## Vehicle trim acquisition

No single free source should be treated as complete trim truth. Build a
multi-source entity-resolution pipeline instead.

1. **NHTSA vPIC** — government/manufacturer-submitted VIN and vehicle identity
   evidence. The downloadable PostgreSQL database is useful for offline VIN
   decoding; vPIC APIs remain necessary for broader make/model/attribute data.
2. **eBay Motors compatibility metadata** — useful structured taxonomy for
   Year/Make/Model/Trim/Engine combinations used in US Motors parts
   compatibility. Treat as retailer/catalog evidence and corroborate before
   canonical promotion.
3. **OEM parts/service sources** — highest-value evidence when terms permit
   automated collection. Exact OEM applicability can support stronger
   promotion under PartGraph source policy.
4. **Open vehicle repositories** — discovery/corroboration only unless their
   provenance and license support stronger use. Candidate projects reviewed
   include `plowman/open-vehicle-db`, `vehiclesdb/vehiclesdb`, and
   `gor3a/vehicle-makes-models`.
5. **Vehicle listing datasets** — listings often contain marketing trims and
   VINs, making them useful for entity-resolution research. Commercial-use
   licensing must be checked before production ingestion. Rebrowser's
   AutoTrader/Cars.com datasets are examples of this category.

A trim candidate should be keyed by as much identity context as is available:
year, market, make, model, generation/body style, trim/submodel, engine,
transmission, drivetrain, and source-specific identifiers. Do not collapse two
records solely because Year/Make/Model/Trim matches.

## Parts, fitment, and inventory acquisition

### eBay Motors

The first implemented collector uses official eBay APIs:

- Metadata API compatibility property values to enumerate Trim and Engine
  values under Year/Make/Model/category filters.
- Browse API compatibility search to capture live parts offers and returned
  compatibility properties.

Each Browse result can produce three independent observations:

1. an `inventory_offer_candidate` for price/condition/availability discovery;
2. a `part_candidate` for title, brand, MPN and identifiers;
3. a `part_fitment_candidate` when compatibility properties are returned.

Retailer compatibility remains candidate evidence. It must not silently become
canonical fitment.

### ACES / PIES

Auto Care ACES is the industry standard for communicating fitment and PIES for
product information. Their schemas are useful targets for PartGraph's future
normalized part/fitment model, but ACES/VCdb are not themselves a universal
free parts-fitment catalog. Supporting reference databases and commercial feeds
have separate access/licensing requirements.

When licensed ACES feeds become available, use an ACES parser/validator and
stage the original XML plus extracted applications/part numbers. Open tooling
such as `autopartsource/aceslint` is useful engineering reference material.

## Unstructured data purification

Unstructured collection is acceptable and desirable when the source is legal
to collect and provenance is retained. The purifier should be a repeatable,
versioned pipeline rather than a destructive cleanup step:

1. ingest raw HTML/JSON/XML/CSV/text/document metadata;
2. fingerprint and deduplicate exact source observations;
3. detect/extract entities (vehicle, trim, engine, part number, brand, offer);
4. normalize strings/units without deleting the original representation;
5. resolve entities using deterministic keys first, probabilistic/embedding or
   LLM-assisted matching second;
6. retain conflicts and alternate values with their provenance;
7. score extraction confidence separately from source authority;
8. promote only when source policy and corroboration thresholds permit it.

This avoids the classic data-lake failure mode where a lake becomes a data
swamp because raw records lack metadata, lineage, discoverability, and stable
promotion rules.

## Running the eBay collector

Do not commit API credentials. Configure one of:

- `EBAY_ACCESS_TOKEN`, or
- `EBAY_CLIENT_ID` and `EBAY_CLIENT_SECRET`

Use a database connection whose role is restricted to the collector staging
boundary.

```bash
cd api
python -m partgraph.collectors.cli trims \
  --year 2012 --make Honda --model Civic --category-id 33707

python -m partgraph.collectors.cli inventory \
  --query "brake pads" --category-id 33559 \
  --year 2012 --make Honda --model Civic \
  --trim "EX Sedan 4-Door" \
  --engine "1.8L 1799CC l4 GAS SOHC Naturally Aspirated"
```

The commands stage raw observations only. They do not populate canonical part
or fitment tables.

## Next schema work

Do not design the final normalized parts schema from one retailer response.
After collecting representative OEM, retailer, and ACES-shaped observations,
infer the Silver schema from the recurring fields. Expected entities include:

- part identity / manufacturer part number;
- alternate and superseded part numbers;
- brand/manufacturer;
- part type/category/position;
- vehicle application / fitment edge;
- qualifier/constraint;
- seller/supplier;
- inventory offer snapshot;
- price/currency/condition/quantity/location;
- source evidence and observation history.

Keep inventory temporal: an offer observed today is an observation, not a
permanent property of a part.
