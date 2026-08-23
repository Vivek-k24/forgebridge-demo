-- PartGraph catalog schema (SQLite / Cloudflare D1 compatible)
-- This schema stores identity/fitment evidence. It does NOT store inferred repair procedures.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS catalog_sources (
  id TEXT PRIMARY KEY,
  url TEXT NOT NULL UNIQUE,
  domain TEXT NOT NULL,
  source_type TEXT NOT NULL CHECK (source_type IN (
    'honda-official',
    'government',
    'dealer-catalog',
    'catalog-retailer',
    'manufacturer',
    'marketplace'
  )),
  trust_use TEXT NOT NULL CHECK (trust_use IN (
    'vehicle-metadata',
    'part-identity',
    'fitment-evidence',
    'shopping-only'
  )),
  rights_status TEXT NOT NULL DEFAULT 'review-required' CHECK (rights_status IN (
    'review-required',
    'api-authorized',
    'public-facts-only',
    'licensed'
  )),
  market TEXT,
  notes TEXT,
  last_checked_at TEXT
);

CREATE TABLE IF NOT EXISTS vehicle_configs (
  id TEXT PRIMARY KEY,
  make TEXT NOT NULL,
  year INTEGER NOT NULL,
  model TEXT NOT NULL,
  trim TEXT,
  series TEXT,
  body TEXT,
  engine TEXT,
  transmission TEXT,
  market TEXT NOT NULL,
  source_id TEXT,
  source_external_id TEXT,
  FOREIGN KEY (source_id) REFERENCES catalog_sources(id)
);

CREATE INDEX IF NOT EXISTS idx_vehicle_lookup
  ON vehicle_configs(make, year, model, trim, market);

CREATE TABLE IF NOT EXISTS parts (
  id TEXT PRIMARY KEY,
  manufacturer TEXT NOT NULL DEFAULT 'Honda',
  oem_number TEXT NOT NULL UNIQUE,
  canonical_name TEXT,
  superseded_by_part_id TEXT,
  status TEXT NOT NULL DEFAULT 'candidate' CHECK (status IN ('candidate', 'verified', 'retired')),
  FOREIGN KEY (superseded_by_part_id) REFERENCES parts(id)
);

CREATE INDEX IF NOT EXISTS idx_parts_oem_number ON parts(oem_number);

CREATE TABLE IF NOT EXISTS part_fitment_observations (
  id TEXT PRIMARY KEY,
  part_id TEXT NOT NULL,
  vehicle_config_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  observed_name TEXT,
  observed_quantity INTEGER,
  evidence_text TEXT,
  evidence_locator TEXT,
  observed_at TEXT NOT NULL,
  review_status TEXT NOT NULL DEFAULT 'candidate' CHECK (review_status IN (
    'candidate',
    'corroborated',
    'verified',
    'rejected'
  )),
  FOREIGN KEY (part_id) REFERENCES parts(id),
  FOREIGN KEY (vehicle_config_id) REFERENCES vehicle_configs(id),
  FOREIGN KEY (source_id) REFERENCES catalog_sources(id)
);

CREATE INDEX IF NOT EXISTS idx_fitment_vehicle ON part_fitment_observations(vehicle_config_id);
CREATE INDEX IF NOT EXISTS idx_fitment_part ON part_fitment_observations(part_id);

CREATE TABLE IF NOT EXISTS part_media_refs (
  id TEXT PRIMARY KEY,
  part_id TEXT NOT NULL,
  source_id TEXT NOT NULL,
  remote_url TEXT NOT NULL,
  media_type TEXT NOT NULL CHECK (media_type IN ('product-photo', 'diagram', 'installed-photo')),
  rights_status TEXT NOT NULL DEFAULT 'reference-only' CHECK (rights_status IN (
    'reference-only',
    'licensed',
    'owned',
    'user-opt-in'
  )),
  sha256 TEXT,
  FOREIGN KEY (part_id) REFERENCES parts(id),
  FOREIGN KEY (source_id) REFERENCES catalog_sources(id)
);

CREATE TABLE IF NOT EXISTS catalog_scrape_runs (
  id TEXT PRIMARY KEY,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  source_id TEXT NOT NULL,
  http_status INTEGER,
  robots_allowed INTEGER,
  extracted_part_count INTEGER NOT NULL DEFAULT 0,
  error_text TEXT,
  FOREIGN KEY (source_id) REFERENCES catalog_sources(id)
);

-- Mechanical/service truth belongs in a separate verified story/table set later.
-- Do not derive torque, pressure, fluid type/quantity, removal sequence, safety procedure,
-- metallurgy, or repair relationships from seller/catalog text alone.
