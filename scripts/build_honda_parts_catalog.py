#!/usr/bin/env python3
"""Build a provenance-preserving Honda parts catalog database for PartGraph.

The collector starts from the exact Honda vehicle configurations already generated
under ``public/data/honda/years/*.json``. For one exact configuration it:

1. fetches the vehicle catalog page,
2. discovers that configuration's parts-list / assembly pages,
3. extracts factual OEM-number/name/quantity observations,
4. writes those observations to SQLite with source provenance.

Trust boundary
--------------
This tool creates *candidate catalog observations only*. It does not infer repair
procedures, part-to-part mechanical relationships, torque, fluids, pressure,
metallurgy, fastener reuse, interchange, or safety facts. Public catalog pages
are corroborating evidence, not American Honda OEM authority. robots.txt is
checked before network retrieval but is not a substitute for terms/licensing
review.

The program uses only the Python standard library and zero LLM tokens.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "catalog" / "honda-parts.sqlite"
DEFAULT_SCHEMA = ROOT / "catalog" / "schema.sql"
DEFAULT_CACHE = ROOT / ".cache" / "partgraph" / "honda-parts"
CATALOG_YEARS = ROOT / "public" / "data" / "honda" / "years"
USER_AGENT = "PartGraphCatalogResearch/0.2 (+https://github.com/Vivek-k24/forgebridge-demo)"
DEFAULT_DELAY_SECONDS = 1.25
PART_NUMBER_RE = re.compile(r"\b([0-9A-Z]{5}-[0-9A-Z]{3}-[0-9A-Z]{3})\b", re.IGNORECASE)
QUANTITY_RES = (
    re.compile(r"Require\s+Quantity\s*:\s*(\d+)", re.IGNORECASE),
    re.compile(r"\bQty(?:uantity)?\s*[:x]?\s*(\d+)\b", re.IGNORECASE),
)
BLOCK_TAGS = {
    "br", "p", "div", "li", "tr", "td", "th", "section", "article",
    "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stable_id(prefix: str, *values: object) -> str:
    payload = "\x1f".join(str(value) for value in values)
    return f"{prefix}_{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]}"


def slug_label(value: str) -> str:
    cleaned = re.sub(r"\.html?$", "", value, flags=re.IGNORECASE).replace("-", "_")
    acronyms = {"a": "A", "c": "C", "abs": "ABS", "srs": "SRS", "vsa": "VSA", "cvt": "CVT"}
    return " ".join(acronyms.get(word.lower(), word.title()) for word in cleaned.split("_") if word)


class CatalogHTMLParser(HTMLParser):
    """Extract links, image references and readable text with stdlib only."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._text_parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self.images: list[tuple[str, str]] = []
        self._anchor_href: str | None = None
        self._anchor_text: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_dict = {key.lower(): value for key, value in attrs}
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in BLOCK_TAGS:
            self._text_parts.append("\n")
        if tag == "a":
            self._anchor_href = attrs_dict.get("href")
            self._anchor_text = []
        if tag == "img":
            src = attrs_dict.get("src") or attrs_dict.get("data-src") or attrs_dict.get("data-original")
            if src:
                self.images.append((src, attrs_dict.get("alt") or ""))

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "a" and self._anchor_href:
            text = " ".join("".join(self._anchor_text).split())
            self.links.append((self._anchor_href, text))
            self._anchor_href = None
            self._anchor_text = []
        if tag in BLOCK_TAGS:
            self._text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._anchor_href is not None:
            self._anchor_text.append(data)
        self._text_parts.append(data)

    @property
    def lines(self) -> list[str]:
        text = html.unescape("".join(self._text_parts))
        return [" ".join(line.split()) for line in text.splitlines() if " ".join(line.split())]


@dataclass(frozen=True)
class VehicleConfig:
    key: str
    year: int
    model: str
    body_trim: str
    emission_transmission: str
    source_url: str
    market: str

    @property
    def database_id(self) -> str:
        return f"hpn:{self.key}"


@dataclass(frozen=True)
class AssemblyPage:
    url: str
    category_slug: str
    assembly_slug: str
    link_text: str

    @property
    def category_label(self) -> str:
        return slug_label(self.category_slug)

    @property
    def assembly_label(self) -> str:
        return self.link_text.strip() or slug_label(self.assembly_slug)


@dataclass(frozen=True)
class PartCandidate:
    oem_number: str
    observed_name: str | None
    observed_quantity: int | None
    evidence_text: str
    image_url: str | None = None


def load_vehicle_config(
    year: int,
    model: str,
    config_key: str | None,
    configuration_contains: str | None,
) -> VehicleConfig:
    path = CATALOG_YEARS / f"{year}.json"
    if not path.exists():
        raise RuntimeError(f"Vehicle catalog file is missing: {path}. Run scripts/build_honda_catalog.py first.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    model_normalized = model.casefold().strip()
    matches = [
        record for record in payload.get("records", [])
        if str(record.get("model", "")).casefold() == model_normalized
    ]
    if config_key:
        matches = [record for record in matches if record.get("key") == config_key]
    if configuration_contains:
        needle = configuration_contains.casefold()
        matches = [
            record for record in matches
            if needle in str(record.get("configurationLabel", "")).casefold()
        ]
    if not matches:
        raise RuntimeError("No exact vehicle configuration matched the requested year/model/configuration.")
    if len(matches) != 1:
        labels = "\n".join(
            f"  {item['key']}  {item.get('configurationLabel', '')}" for item in matches[:25]
        )
        raise RuntimeError(
            f"{len(matches)} configurations match. Use --config-key or --configuration-contains to select exactly one.\n{labels}"
        )
    item = matches[0]
    return VehicleConfig(
        key=item["key"],
        year=int(item["year"]),
        model=item["model"],
        body_trim=item.get("bodyTrim", ""),
        emission_transmission=item.get("emissionTransmission", ""),
        source_url=item["sourceUrl"],
        market=item.get("market", "catalog-coded"),
    )


class Fetcher:
    """Rate-limited, robots-aware HTTP fetcher with an uncommitted disk cache."""

    def __init__(self, cache_dir: Path, delay_seconds: float, refresh: bool, offline: bool) -> None:
        self.cache_dir = cache_dir
        self.delay_seconds = max(0.0, delay_seconds)
        self.refresh = refresh
        self.offline = offline
        self._last_network_at = 0.0
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}.html"

    def _robot_parser(self, url: str) -> urllib.robotparser.RobotFileParser:
        split = urllib.parse.urlsplit(url)
        origin = f"{split.scheme}://{split.netloc}"
        if origin in self._robots:
            return self._robots[origin]
        robots_url = urllib.parse.urljoin(origin, "/robots.txt")
        parser = urllib.robotparser.RobotFileParser(robots_url)
        if self.offline:
            parser.parse(["User-agent: *", "Disallow:"])
        else:
            request = urllib.request.Request(
                robots_url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/plain"},
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    body = response.read().decode("utf-8", errors="replace")
                parser.parse(body.splitlines())
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
                raise RuntimeError(f"Unable to verify robots.txt for {origin}: {exc}") from exc
        self._robots[origin] = parser
        return parser

    def fetch_text(self, url: str) -> tuple[str, bool]:
        cache_path = self._cache_path(url)
        if cache_path.exists() and not self.refresh:
            return cache_path.read_text(encoding="utf-8", errors="replace"), True
        if self.offline:
            raise RuntimeError(f"Offline cache miss: {url}")
        if not self._robot_parser(url).can_fetch(USER_AGENT, url):
            raise RuntimeError(f"robots.txt does not permit automated retrieval of {url}")
        elapsed = time.monotonic() - self._last_network_at
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                content_type = response.headers.get_content_type()
                if content_type not in {"text/html", "application/xhtml+xml"}:
                    raise RuntimeError(f"Unexpected content type {content_type!r} for {url}")
                charset = response.headers.get_content_charset() or "utf-8"
                body = response.read().decode(charset, errors="replace")
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            raise RuntimeError(f"Unable to fetch {url}: {exc}") from exc
        self._last_network_at = time.monotonic()
        cache_path.write_text(body, encoding="utf-8")
        return body, False


def discover_assembly_pages(vehicle_url: str, page_html: str) -> list[AssemblyPage]:
    parser = CatalogHTMLParser()
    parser.feed(page_html)
    vehicle_slug = Path(urllib.parse.urlsplit(vehicle_url).path).name.removesuffix("-parts.html")
    marker = f"/parts-list/{vehicle_slug}/"
    host = urllib.parse.urlsplit(vehicle_url).netloc.lower()
    discovered: dict[str, AssemblyPage] = {}
    for href, text in parser.links:
        absolute = urllib.parse.urljoin(vehicle_url, href)
        split = urllib.parse.urlsplit(absolute)
        if split.netloc.lower() != host or marker not in split.path or not split.path.lower().endswith(".html"):
            continue
        remainder = split.path.split(marker, 1)[1]
        segments = [segment for segment in remainder.split("/") if segment]
        if len(segments) < 2:
            continue
        clean = urllib.parse.urlunsplit((split.scheme, split.netloc, split.path, "", ""))
        discovered[clean] = AssemblyPage(
            url=clean,
            category_slug=segments[-2],
            assembly_slug=segments[-1].removesuffix(".html"),
            link_text=text,
        )
    return sorted(discovered.values(), key=lambda item: (item.category_slug, item.assembly_slug, item.url))


def looks_like_noise(line: str) -> bool:
    value = line.strip()
    return bool(
        re.match(r"^\$\s*\d", value)
        or re.match(
            r"^(add to cart|view details|view|price|msrp|sort by|ref no\.?|part no\.?|change vehicle)$",
            value,
            re.I,
        )
        or re.match(r"^(package quantity|require quantity)\s*:", value, re.I)
        or re.fullmatch(r"\d+", value)
    )


def infer_name(lines: Sequence[str], index: int, part_number: str) -> str | None:
    same = lines[index]
    position = same.upper().find(part_number.upper())
    if position >= 0:
        before = same[:position].strip(" :-|")
        after = same[position + len(part_number):].strip(" :-|")
        for candidate in (after, before):
            if candidate and not looks_like_noise(candidate) and not PART_NUMBER_RE.search(candidate):
                return candidate[:180]
    for offset in (1, 2, 3, 4, 5, -1, -2, -3):
        candidate_index = index + offset
        if candidate_index < 0 or candidate_index >= len(lines):
            continue
        candidate = lines[candidate_index]
        if candidate and not looks_like_noise(candidate) and not PART_NUMBER_RE.search(candidate):
            return candidate[:180]
    return None


def infer_quantity(lines: Sequence[str], index: int) -> int | None:
    for offset in range(0, 9):
        candidate_index = index + offset
        if candidate_index >= len(lines):
            break
        for regex in QUANTITY_RES:
            match = regex.search(lines[candidate_index])
            if match:
                return int(match.group(1))
    return None


def choose_reference_image(parser: CatalogHTMLParser, page_url: str, oem_number: str) -> str | None:
    normalized = oem_number.replace("-", "").lower()
    for src, alt in parser.images:
        if normalized in f"{src} {alt}".replace("-", "").lower():
            return urllib.parse.urljoin(page_url, src)
    return None


def extract_part_candidates(page_url: str, page_html: str) -> list[PartCandidate]:
    parser = CatalogHTMLParser()
    parser.feed(page_html)
    lines = parser.lines
    candidates: dict[str, PartCandidate] = {}
    for index, line in enumerate(lines):
        for match in PART_NUMBER_RE.finditer(line):
            oem = match.group(1).upper()
            if oem in candidates:
                continue
            evidence = " | ".join(lines[max(0, index - 2): min(len(lines), index + 7)])[:900]
            candidates[oem] = PartCandidate(
                oem_number=oem,
                observed_name=infer_name(lines, index, oem),
                observed_quantity=infer_quantity(lines, index),
                evidence_text=evidence,
                image_url=choose_reference_image(parser, page_url, oem),
            )
    return sorted(candidates.values(), key=lambda item: item.oem_number)


def open_database(path: Path, schema_path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.executescript(schema_path.read_text(encoding="utf-8"))
    return connection


def upsert_vehicle(connection: sqlite3.Connection, vehicle: VehicleConfig) -> None:
    connection.execute(
        """
        INSERT INTO vehicle_configs (
          id, make, year, model, trim, series, body, engine, transmission, market,
          source_id, source_external_id
        ) VALUES (?, 'Honda', ?, ?, ?, ?, ?, NULL, ?, ?, NULL, ?)
        ON CONFLICT(id) DO UPDATE SET
          year=excluded.year, model=excluded.model, trim=excluded.trim,
          series=excluded.series, body=excluded.body, transmission=excluded.transmission,
          market=excluded.market, source_external_id=excluded.source_external_id
        """,
        (
            vehicle.database_id,
            vehicle.year,
            vehicle.model,
            vehicle.body_trim,
            vehicle.emission_transmission,
            vehicle.body_trim,
            vehicle.emission_transmission,
            vehicle.market,
            vehicle.key,
        ),
    )


def upsert_source(connection: sqlite3.Connection, page_url: str, market: str, note: str) -> str:
    existing = connection.execute("SELECT id FROM catalog_sources WHERE url = ?", (page_url,)).fetchone()
    if existing:
        source_id = existing[0]
        connection.execute(
            "UPDATE catalog_sources SET last_checked_at = ?, notes = ? WHERE id = ?",
            (utc_now(), note, source_id),
        )
        return source_id
    source_id = stable_id("src", page_url)
    connection.execute(
        """
        INSERT INTO catalog_sources (
          id, url, domain, source_type, trust_use, rights_status, market, notes, last_checked_at
        ) VALUES (?, ?, ?, 'catalog-retailer', 'fitment-evidence', 'review-required', ?, ?, ?)
        """,
        (
            source_id,
            page_url,
            urllib.parse.urlsplit(page_url).netloc.lower(),
            market,
            note,
            utc_now(),
        ),
    )
    return source_id


def upsert_assembly(
    connection: sqlite3.Connection,
    vehicle: VehicleConfig,
    assembly: AssemblyPage,
    source_id: str,
) -> str:
    assembly_id = stable_id("assembly", vehicle.database_id, assembly.url)
    connection.execute(
        """
        INSERT INTO assemblies (
          id, vehicle_config_id, category_slug, category_name, assembly_slug,
          assembly_name, source_id, source_url, review_status, observed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'candidate', ?)
        ON CONFLICT(id) DO UPDATE SET
          category_name=excluded.category_name,
          assembly_name=excluded.assembly_name,
          source_id=excluded.source_id,
          source_url=excluded.source_url,
          observed_at=excluded.observed_at
        """,
        (
            assembly_id,
            vehicle.database_id,
            assembly.category_slug,
            assembly.category_label,
            assembly.assembly_slug,
            assembly.assembly_label,
            source_id,
            assembly.url,
            utc_now(),
        ),
    )
    return assembly_id


def store_candidate(
    connection: sqlite3.Connection,
    vehicle: VehicleConfig,
    assembly_id: str,
    source_id: str,
    candidate: PartCandidate,
) -> None:
    part_id = stable_id("part", candidate.oem_number)
    connection.execute(
        """
        INSERT INTO parts (id, manufacturer, oem_number, canonical_name, status)
        VALUES (?, 'Honda', ?, ?, 'candidate')
        ON CONFLICT(oem_number) DO UPDATE SET
          canonical_name=CASE
            WHEN parts.canonical_name IS NULL OR parts.canonical_name = '' THEN excluded.canonical_name
            ELSE parts.canonical_name
          END
        """,
        (part_id, candidate.oem_number, candidate.observed_name),
    )
    actual_part_id = connection.execute(
        "SELECT id FROM parts WHERE oem_number = ?", (candidate.oem_number,)
    ).fetchone()[0]
    observation_id = stable_id("obs", actual_part_id, vehicle.database_id, source_id)
    connection.execute(
        """
        INSERT INTO part_fitment_observations (
          id, part_id, vehicle_config_id, source_id, observed_name,
          observed_quantity, evidence_text, evidence_locator, observed_at, review_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'candidate')
        ON CONFLICT(id) DO UPDATE SET
          observed_name=excluded.observed_name,
          observed_quantity=excluded.observed_quantity,
          evidence_text=excluded.evidence_text,
          evidence_locator=excluded.evidence_locator,
          observed_at=excluded.observed_at
        """,
        (
            observation_id,
            actual_part_id,
            vehicle.database_id,
            source_id,
            candidate.observed_name,
            candidate.observed_quantity,
            candidate.evidence_text,
            "public-catalog-visible-text",
            utc_now(),
        ),
    )
    assembly_observation_id = stable_id("aobs", assembly_id, actual_part_id, source_id)
    connection.execute(
        """
        INSERT INTO assembly_part_observations (
          id, assembly_id, part_id, fitment_observation_id, source_id, observed_at, review_status
        ) VALUES (?, ?, ?, ?, ?, ?, 'candidate')
        ON CONFLICT(id) DO UPDATE SET observed_at=excluded.observed_at
        """,
        (assembly_observation_id, assembly_id, actual_part_id, observation_id, source_id, utc_now()),
    )
    if candidate.image_url:
        media_id = stable_id("media", actual_part_id, source_id, candidate.image_url)
        connection.execute(
            """
            INSERT INTO part_media_refs (
              id, part_id, source_id, remote_url, media_type, rights_status, sha256
            ) VALUES (?, ?, ?, ?, 'product-photo', 'reference-only', NULL)
            ON CONFLICT(id) DO NOTHING
            """,
            (media_id, actual_part_id, source_id, candidate.image_url),
        )


def run_collection(args: argparse.Namespace) -> int:
    vehicle = load_vehicle_config(args.year, args.model, args.config_key, args.configuration_contains)
    print(
        f"[parts] vehicle: {vehicle.key} ({vehicle.body_trim} · {vehicle.emission_transmission})",
        file=sys.stderr,
    )
    fetcher = Fetcher(Path(args.cache_dir), args.delay, args.refresh, args.offline)
    vehicle_html, vehicle_cache_hit = fetcher.fetch_text(vehicle.source_url)
    assemblies = discover_assembly_pages(vehicle.source_url, vehicle_html)
    if not assemblies:
        raise RuntimeError("No parts-list assembly pages were discovered. The source site structure may have changed.")
    if args.assembly_contains:
        needle = args.assembly_contains.casefold()
        assemblies = [
            item for item in assemblies
            if needle in f"{item.category_label} {item.assembly_label} {item.url}".casefold()
        ]
    if args.max_assemblies is not None:
        assemblies = assemblies[:args.max_assemblies]
    if not assemblies:
        raise RuntimeError("Assembly filters matched zero pages.")

    connection = open_database(Path(args.db), Path(args.schema))
    try:
        upsert_vehicle(connection, vehicle)
        totals = {"assemblies": 0, "parts": 0, "cache_hits": int(vehicle_cache_hit), "errors": 0}
        for position, assembly in enumerate(assemblies, start=1):
            print(
                f"[parts] {position}/{len(assemblies)} {assembly.category_label} / {assembly.assembly_label}",
                file=sys.stderr,
            )
            source_id = upsert_source(
                connection,
                assembly.url,
                vehicle.market,
                "Public catalog candidate evidence only; not American Honda OEM authority and not repair/service truth.",
            )
            run_id = stable_id("run", source_id, utc_now(), position)
            started_at = utc_now()
            try:
                page_html, cache_hit = fetcher.fetch_text(assembly.url)
                totals["cache_hits"] += int(cache_hit)
                candidates = extract_part_candidates(assembly.url, page_html)
                assembly_id = upsert_assembly(connection, vehicle, assembly, source_id)
                for candidate in candidates:
                    store_candidate(connection, vehicle, assembly_id, source_id, candidate)
                connection.execute(
                    """
                    INSERT INTO catalog_scrape_runs (
                      id, started_at, finished_at, source_id, http_status,
                      robots_allowed, extracted_part_count, error_text
                    ) VALUES (?, ?, ?, ?, 200, 1, ?, NULL)
                    """,
                    (run_id, started_at, utc_now(), source_id, len(candidates)),
                )
                totals["assemblies"] += 1
                totals["parts"] += len(candidates)
                connection.commit()
            except Exception as exc:
                totals["errors"] += 1
                connection.execute(
                    """
                    INSERT INTO catalog_scrape_runs (
                      id, started_at, finished_at, source_id, http_status,
                      robots_allowed, extracted_part_count, error_text
                    ) VALUES (?, ?, ?, ?, NULL, 0, 0, ?)
                    """,
                    (run_id, started_at, utc_now(), source_id, str(exc)[:1000]),
                )
                connection.commit()
                print(f"[parts] skipped: {exc}", file=sys.stderr)
                if args.fail_fast:
                    raise
        unique_parts = connection.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
        unique_assemblies = connection.execute("SELECT COUNT(*) FROM assemblies").fetchone()[0]
        print(
            f"[parts] stored {totals['parts']} observations from {totals['assemblies']} assembly pages; "
            f"database now has {unique_parts} unique part numbers and {unique_assemblies} assemblies; "
            f"cache hits={totals['cache_hits']}, errors={totals['errors']}",
            file=sys.stderr,
        )
        print(Path(args.db).resolve())
        return 0 if totals["assemblies"] else 2
    finally:
        connection.close()


SELF_TEST_HTML = """
<html><body>
<h1>Radiator (Denso)</h1>
<div>19010-RRH-901</div><div>Radiator (Denso)</div><div>Require Quantity: 1</div>
<div>74171-SNA-A00</div><div>Bracket, Radiator Mounting</div><div>Qty: 2</div>
</body></html>
"""

SELF_TEST_VEHICLE_HTML = """
<html><body>
<a href="/parts-list/2009-honda-civic--4dr_mx_hybrid-ka_cvt/electrical_exhaust_heater_fuel/radiator_denso.html">Radiator (Denso)</a>
<a href="/parts-list/2009-honda-civic--4dr_mx_hybrid-ka_cvt/body_air_conditioning/a_c_condenser.html">A/C Condenser</a>
<a href="https://example.com/not-ours">Other</a>
</body></html>
"""


def self_test(schema_path: Path) -> int:
    vehicle_url = "https://www.hondapartsnow.com/2009-honda-civic--4dr_mx_hybrid-ka_cvt-parts.html"
    pages = discover_assembly_pages(vehicle_url, SELF_TEST_VEHICLE_HTML)
    assert len(pages) == 2, pages
    candidates = extract_part_candidates(pages[0].url, SELF_TEST_HTML)
    by_number = {item.oem_number: item for item in candidates}
    assert set(by_number) == {"19010-RRH-901", "74171-SNA-A00"}, by_number
    assert by_number["19010-RRH-901"].observed_quantity == 1
    assert by_number["74171-SNA-A00"].observed_quantity == 2
    assert "Radiator" in (by_number["19010-RRH-901"].observed_name or "")

    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(schema_path.read_text(encoding="utf-8"))
    vehicle = VehicleConfig(
        key="2009:civic:4dr_mx_hybrid:ka_cvt",
        year=2009,
        model="Civic",
        body_trim="4 Door MX Hybrid",
        emission_transmission="KA CVT",
        source_url=vehicle_url,
        market="catalog-coded",
    )
    upsert_vehicle(connection, vehicle)
    source_id = upsert_source(connection, pages[0].url, vehicle.market, "self-test")
    assembly_id = upsert_assembly(connection, vehicle, pages[0], source_id)
    for candidate in candidates:
        store_candidate(connection, vehicle, assembly_id, source_id, candidate)
    assert connection.execute("SELECT COUNT(*) FROM parts").fetchone()[0] == 2
    assert connection.execute("SELECT COUNT(*) FROM assemblies").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM assembly_part_observations").fetchone()[0] == 2
    connection.close()
    print("Honda parts catalog self-test passed: discovery, extraction, schema, and persistence.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Retrieve candidate Honda parts catalog pages and build a SQLite database."
    )
    parser.add_argument("--year", type=int, help="Honda model year from the generated vehicle catalog")
    parser.add_argument("--model", help="Honda model name, for example Civic")
    parser.add_argument("--config-key", help="Exact configuration key from public/data/honda/years/<year>.json")
    parser.add_argument(
        "--configuration-contains",
        help="Case-insensitive text that must occur in the configuration label",
    )
    parser.add_argument(
        "--assembly-contains",
        help="Only collect assemblies whose name/category/URL contains this text",
    )
    parser.add_argument(
        "--max-assemblies",
        type=int,
        default=None,
        help="Safety cap on assembly pages for this run",
    )
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite output path")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="Catalog schema path")
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE), help="Local uncommitted HTTP cache")
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help="Minimum seconds between network page requests",
    )
    parser.add_argument("--refresh", action="store_true", help="Ignore cached HTML and fetch again")
    parser.add_argument("--offline", action="store_true", help="Use cache only; make no network requests")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on the first assembly retrieval/parse error")
    parser.add_argument("--self-test", action="store_true", help="Run deterministic offline parser/database tests")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.self_test:
        return self_test(Path(args.schema))
    if args.year is None or not args.model:
        parser.error("--year and --model are required unless --self-test is used")
    return run_collection(args)


if __name__ == "__main__":
    raise SystemExit(main())
