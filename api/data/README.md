# API data assets

This directory contains versioned datasets that are still required by the current PartGraph code or by immutable migration history.

## Retained legacy workbook

`Selected_Asian_Brands_1996_2000.xlsx` is intentionally retained only because historical Alembic revisions `0017_selected_asian_workbook.py` and `0020_catalog_coverage.py` read this exact API path when reconstructing the legacy migration chain. Migration `0060_retire_selected_asian_workbook.py` removes that lineage from current persistent data, but it does not make the historical migration artifact removable.

The workbook is not authoritative automotive truth and must not be republished as verified canonical data. Its original source remains preserved by Git history at commit `ab954125d89f8ae4cfc42d35af177ec1fe3938a8`.

The duplicate working-tree copy previously under `docs/` and the unused `api/data/archive/reference_fleet_legacy/` datasets were removed after dependency review. Their historical contents remain recoverable from Git history.

Current canonical/reference datasets belong under `api/data/reference/`, while generic equipment catalog data belongs under `api/data/equipment/`.
