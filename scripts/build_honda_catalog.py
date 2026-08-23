#!/usr/bin/env python3
"""Build a deterministic Honda vehicle-configuration catalog for PartGraph.

The collector prefers HondaPartsNow's XML sitemap because sitemap discovery is
far cheaper and less intrusive than scraping vehicle pages one at a time.  The
vehicle configuration itself is encoded in the catalog URL, for example:

  2009-honda-civic--4dr_ex_l-ka_5at-parts.html

The generated data preserves the source slug and source URL so every PartGraph
selection can be checked against the catalog that produced it.  This script
uses no LLM and no third-party Python packages.
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

SOURCE_ROOT = "https://www.hondapartsnow.com"
START_SITEMAPS = [f"{SOURCE_ROOT}/sitemap.xml"]
USER_AGENT = "PartGraphCatalogResearch/0.1 (+https://github.com/Vivek-k24/forgebridge-demo)"
CONFIG_RE = re.compile(
    r"^https://www\.hondapartsnow\.com/(?P<year>\d{4})-honda-(?P<model>.+?)--(?P<config>.+)-parts\.html/?$",
    re.IGNORECASE,
)

MODEL_NAMES = {
    "accord": "Accord", "accord_hybrid": "Accord Hybrid", "civic": "Civic", "civic_hybrid": "Civic Hybrid",
    "clarity_electric": "Clarity Electric", "clarity_fuel_cell": "Clarity Fuel Cell", "clarity_plug_in_hybrid": "Clarity Plug-In Hybrid",
    "cr_v": "CR-V", "cr_v_hybrid": "CR-V Hybrid", "cr_z": "CR-Z", "crosstour": "Crosstour", "crx": "CRX",
    "del_sol": "Del Sol", "element": "Element", "fit": "Fit", "fit_ev": "Fit EV", "hr_v": "HR-V", "insight": "Insight",
    "odyssey": "Odyssey", "passport": "Passport", "pilot": "Pilot", "prelude": "Prelude", "prologue": "Prologue",
    "ridgeline": "Ridgeline", "s2000": "S2000",
}
BODY_TOKENS = {"2dr": "2 Door", "3dr": "3 Door", "4dr": "4 Door", "5dr": "5 Door", "2wd": "2WD", "4wd": "4WD", "awd": "AWD"}
KNOWN_PHRASES = {
    "ex_l": "EX-L", "ex_t": "EX-T", "dx_vp": "DX-VP", "lx_p": "LX-P", "lx_s": "LX-S", "sport_l": "Sport-L",
    "type_r": "Type R", "black_edition": "Black Edition", "sport_touring": "Sport Touring", "touring_hybrid": "Touring Hybrid",
    "sport_hybrid": "Sport Hybrid", "sport_l_hybrid": "Sport-L Hybrid", "sport_touring_hybrid": "Sport Touring Hybrid",
    "trail_sport": "TrailSport", "trailsport": "TrailSport", "value_package": "Value Package", "plug_in_hybrid": "Plug-In Hybrid",
    "fuel_cell": "Fuel Cell",
}
UPPER_TOKENS = {"dx", "ex", "lx", "cx", "hx", "gx", "hf", "si", "se", "vp", "rtl", "rt", "rt_l", "touring", "sport", "elite", "hybrid", "base", "black", "edition", "type", "r", "mx"}

@dataclass(frozen=True)
class Record:
    key: str
    year: int
    model: str
    modelSlug: str
    bodyTrim: str
    bodyTrimSlug: str
    emissionTransmission: str
    emissionTransmissionSlug: str
    configurationLabel: str
    sourceUrl: str
    source: str = "HondaPartsNow catalog"
    market: str = "catalog-coded"


def fetch_bytes(url: str, attempts: int = 4) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/xml,text/xml,*/*"})
    delay = 1.0
    last: Exception | None = None
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                return response.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            last = exc
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"Unable to fetch {url}: {last}")


def parse_sitemap_payload(url: str, payload: bytes) -> tuple[list[str], list[str]]:
    if url.endswith(".gz") or payload[:2] == b"\x1f\x8b":
        payload = gzip.decompress(payload)
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise RuntimeError(f"Invalid sitemap XML from {url}: {exc}") from exc
    locs = [(node.text or "").strip() for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "loc"]
    if root.tag.rsplit("}", 1)[-1].lower() == "sitemapindex":
        return locs, []
    return [], locs


def collect_urls(start_urls: Iterable[str], max_sitemaps: int = 500) -> list[str]:
    pending = list(start_urls)
    seen_maps: set[str] = set()
    urls: list[str] = []
    while pending:
        sitemap = pending.pop(0)
        if sitemap in seen_maps:
            continue
        if len(seen_maps) >= max_sitemaps:
            raise RuntimeError(f"Sitemap safety limit exceeded ({max_sitemaps}).")
        seen_maps.add(sitemap)
        print(f"[catalog] sitemap {len(seen_maps)}: {sitemap}", file=sys.stderr)
        child_maps, page_urls = parse_sitemap_payload(sitemap, fetch_bytes(sitemap))
        pending.extend(child for child in child_maps if child not in seen_maps)
        urls.extend(page_urls)
    print(f"[catalog] discovered {len(urls):,} sitemap URLs from {len(seen_maps)} sitemap file(s)", file=sys.stderr)
    return urls


def model_name(slug: str) -> str:
    normalized = slug.lower().replace("-", "_")
    if normalized in MODEL_NAMES:
        return MODEL_NAMES[normalized]
    return " ".join(word.upper() if len(word) <= 3 else word.title() for word in normalized.split("_") if word)


def prettify_body_trim(slug: str) -> str:
    value = slug.lower().strip("_")
    prefix = ""
    for token, label in BODY_TOKENS.items():
        if value == token:
            return label
        if value.startswith(token + "_"):
            prefix = label + " "
            value = value[len(token) + 1:]
            break
    for phrase, label in sorted(KNOWN_PHRASES.items(), key=lambda item: -len(item[0])):
        value = value.replace(phrase, label.replace(" ", "~"))
    tokens = []
    for token in value.split("_"):
        if not token:
            continue
        token = token.replace("~", " ")
        if any(ch.isupper() for ch in token):
            tokens.append(token)
        elif token in BODY_TOKENS:
            tokens.append(BODY_TOKENS[token])
        elif token in UPPER_TOKENS or re.fullmatch(r"[a-z]{1,3}\d*", token):
            tokens.append(token.upper())
        elif token.isdigit():
            tokens.append(token)
        else:
            tokens.append(token.title())
    return (prefix + " ".join(tokens)).strip() or slug


def prettify_emission_transmission(slug: str) -> str:
    bits = [bit for bit in slug.strip("_").split("_") if bit]
    return " ".join(bit.upper() for bit in bits) or slug


def record_from_url(url: str) -> Record | None:
    clean = urllib.parse.urlsplit(url)._replace(query="", fragment="").geturl().rstrip("/")
    match = CONFIG_RE.match(clean)
    if not match:
        return None
    year = int(match.group("year"))
    model_slug = match.group("model").lower().replace("-", "_")
    config = match.group("config").lower()
    if "-" not in config:
        return None
    body_slug, emtrans_slug = config.rsplit("-", 1)
    if not body_slug or not emtrans_slug:
        return None
    body_label = prettify_body_trim(body_slug)
    emtrans_label = prettify_emission_transmission(emtrans_slug)
    display_model = model_name(model_slug)
    key = f"{year}:{model_slug}:{body_slug}:{emtrans_slug}"
    return Record(key=key, year=year, model=display_model, modelSlug=model_slug, bodyTrim=body_label, bodyTrimSlug=body_slug, emissionTransmission=emtrans_label, emissionTransmissionSlug=emtrans_slug, configurationLabel=f"{body_label} · {emtrans_label}", sourceUrl=clean)


def validate(records: list[Record]) -> None:
    if len(records) < 500:
        raise RuntimeError(f"Only {len(records)} exact Honda configuration URLs were found. Refusing to publish a catalog that is probably incomplete.")
    keys = [record.key for record in records]
    urls = [record.sourceUrl for record in records]
    if len(keys) != len(set(keys)):
        raise RuntimeError("Duplicate Honda configuration keys detected.")
    if len(urls) != len(set(urls)):
        raise RuntimeError("Duplicate source URLs detected.")
    if any(record.year < 1970 or record.year > 2035 for record in records):
        raise RuntimeError("Implausible model year detected.")
    if any(not record.bodyTrim or not record.emissionTransmission for record in records):
        raise RuntimeError("Incomplete configuration record detected.")


def write_catalog(records: list[Record], out_dir: Path, sample_size: int = 20) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    year_dir = out_dir / "years"
    year_dir.mkdir(parents=True, exist_ok=True)
    by_year: dict[int, list[Record]] = defaultdict(list)
    for record in records:
        by_year[record.year].append(record)
    models_by_year: dict[str, list[str]] = {}
    model_years: dict[str, list[int]] = defaultdict(list)
    for year, year_records in sorted(by_year.items()):
        models = sorted({record.model for record in year_records})
        models_by_year[str(year)] = models
        for model in models:
            model_years[model].append(year)
        payload = {"year": year, "records": [asdict(record) for record in sorted(year_records, key=lambda r: (r.model, r.configurationLabel, r.sourceUrl))]}
        (year_dir / f"{year}.json").write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    metadata = {
        "schemaVersion": 1, "source": "HondaPartsNow catalog sitemap", "sourceRoot": SOURCE_ROOT,
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "recordCount": len(records),
        "yearCount": len(by_year), "modelCount": len({r.model for r in records}), "years": sorted(by_year),
        "modelsByYear": models_by_year, "yearsByModel": {model: years for model, years in sorted(model_years.items())},
        "identityRule": "year + model + body/trim + emission/transmission; source URL retained for verification", "runtimeLlmTokens": 0,
    }
    (out_dir / "catalog-index.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    rng = random.Random(20260823)
    sample = rng.sample(records, min(sample_size, len(records)))
    (out_dir / "validation-sample.json").write_text(json.dumps({"seed": 20260823, "records": [asdict(record) for record in sample]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    source_ledger = {
        "source": "HondaPartsNow", "purpose": "Public genuine-Honda catalog reference and exact configuration identity", "root": SOURCE_ROOT,
        "collectionMethod": "XML sitemap URL parsing; no LLM",
        "notes": ["PartGraph stores normalized factual identifiers and the original source URL.", "HondaPartsNow is a genuine-parts retailer/catalog reference, not American Honda Motor Co.", "Production/commercial reuse rights require a dedicated terms/licensing review.", "Mechanical repair graphs remain separately verified; this catalog does not make every repair graph complete."],
    }
    (out_dir / "SOURCE.json").write_text(json.dumps(source_ledger, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="public/data/honda", help="Output directory")
    args = parser.parse_args()
    urls = collect_urls(START_SITEMAPS)
    by_key: dict[str, Record] = {}
    for url in urls:
        record = record_from_url(url)
        if record:
            by_key[record.key] = record
    records = sorted(by_key.values(), key=lambda r: (r.year, r.model, r.configurationLabel, r.sourceUrl))
    validate(records)
    write_catalog(records, Path(args.out))
    years = sorted({r.year for r in records})
    models = sorted({r.model for r in records})
    print(f"[catalog] wrote {len(records):,} configurations across {len(years)} years and {len(models)} models", file=sys.stderr)
    print(f"[catalog] year range {years[0]}–{years[-1]}", file=sys.stderr)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
