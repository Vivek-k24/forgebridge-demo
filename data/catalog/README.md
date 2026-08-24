# Generated parts catalog storage

The parts collector introduced in PR #15 writes appendable SQLite catalog data here.

## Main generated files

- `data/catalog/honda-parts.sqlite` — merged parts catalog database.
- `data/catalog/civic-6th-gen-drivetrain-summary.json` — generation-level merge/run summary when produced by the workflow.
- `data/catalog/honda-parts-<year>.sqlite` — temporary per-year shards used by the 1996–2000 Civic generation workflow.
- `data/catalog/civic-6th-gen-drivetrain-<year>-summary.json` — per-year collection summaries.

SQLite files are intentionally gitignored. They contain scraped candidate observations and provenance, not verified repair/service truth.

The collector's HTTP cache is separate and also uncommitted:

- `.cache/partgraph/honda-parts/`

## Full 6th-generation Civic drivetrain collection

```bash
python scripts/build_civic_6th_gen_drivetrain_catalog.py
```

The GitHub Actions workflow collects 1996, 1997, 1998, 1999, and 2000 in parallel, merges the five SQLite shards into `data/catalog/honda-parts.sqlite`, validates foreign keys, and uploads the merged database plus summaries as a workflow artifact.
