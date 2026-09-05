from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from sqlalchemy import delete, func, select

from ..config import settings
from ..database import engine, session_factory
from .catalog_scope import (
    US_IDENTITY_MAKES,
    US_IDENTITY_MARKET,
    US_IDENTITY_YEAR_MAX,
    US_IDENTITY_YEAR_MIN,
    canonical_scoped_make,
)
from .identity_catalog_models import (
    CatalogIdentityModel,
    CatalogIdentityProgress,
    CatalogIdentityTrim,
)

USER_AGENT = (
    "Mozilla/5.0 (compatible; PartGraphIdentityCatalog/1.1; "
    "+local-operator-controlled-catalog-workbench)"
)
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_KBB_BODY_SUFFIX_RE = re.compile(
    r"\s+(?:"
    r"Sport Utility|SUV|Coupe|Sedan|Hatchback|Wagon|Convertible|Roadster|"
    r"Minivan|Van|Pickup|Regular Cab|Extended Cab|Crew Cab|Double Cab|"
    r"Access Cab|SuperCab|SuperCrew|Quad Cab"
    r")(?:\s+\dD)?$",
    re.I,
)
_KBB_EXCLUDED_STYLE_KEYS = {
    "overview",
    "reviews",
    "specs",
    "features",
    "safety",
    "photos",
    "pricing",
    "price",
    "values",
    "recall",
    "recalls",
}
_CARSDIRECT_STYLE_BREAK_RE = re.compile(
    r"\s+(?:"
    r"[2-5]dr\b|2-door\b|3-door\b|4-door\b|5-door\b|"
    r"4x2\b|4x4\b|2wd\b|4wd\b|awd\b|fwd\b|rwd\b|"
    r"front-wheel\b|rear-wheel\b|all-wheel\b"
    r").*$",
    re.I,
)
_CARSDIRECT_EXCLUDED_KEYS = {
    "select a trim",
    "choose a trim",
    "all trims",
}
_SOURCE_MODEL_SUFFIX_TOKENS = {
    "2wd",
    "4wd",
    "awd",
    "fwd",
    "rwd",
    "4x2",
    "4x4",
    "hybrid",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_TOKEN_RE.findall(value.casefold()))


def normalized_key(value: str) -> str:
    return " ".join(_tokens(value))


def slug(value: str) -> str:
    return "-".join(_tokens(value))


def _nhtsa_canonical_map(nhtsa_models: list[str]) -> dict[tuple[str, ...], str]:
    cleaned: dict[tuple[str, ...], str] = {}
    for raw in nhtsa_models:
        label = _SPACE_RE.sub(" ", raw).strip()
        tokens = _tokens(label)
        if label and tokens:
            cleaned.setdefault(tokens, label)

    result: dict[tuple[str, ...], str] = {}
    for tokens, label in cleaned.items():
        # PartGraph models the ordinary vehicle family separately from its
        # hybrid powertrain variant. This matches the accepted Civic Hybrid
        # profile and keeps identities such as 2026 Accord Sport Hybrid under
        # model=Accord rather than inventing model=Accord Hybrid.
        if tokens[-1:] == ("hybrid",) and tokens[:-1] in cleaned:
            result[tokens] = cleaned[tokens[:-1]]
        else:
            result[tokens] = label
    return result


def canonicalize_model_inventory(
    nhtsa_models: list[str],
    fueleconomy_models: list[str],
) -> dict[str, dict[str, list[str]]]:
    inventory: dict[str, dict[str, list[str]]] = {}
    nhtsa_map = _nhtsa_canonical_map(nhtsa_models)

    for raw in nhtsa_models:
        label = _SPACE_RE.sub(" ", raw).strip()
        if not label:
            continue
        canonical = nhtsa_map.get(_tokens(label), label)
        inventory.setdefault(canonical, {}).setdefault("nhtsa_vpic", []).append(label)

    canonical_token_map: dict[tuple[str, ...], str] = {}
    for raw_tokens, canonical in nhtsa_map.items():
        canonical_token_map[raw_tokens] = canonical
        canonical_token_map.setdefault(_tokens(canonical), canonical)
    ordered_nhtsa = sorted(canonical_token_map, key=len, reverse=True)

    for raw in fueleconomy_models:
        label = _SPACE_RE.sub(" ", raw).strip()
        if not label:
            continue
        raw_tokens = _tokens(label)
        canonical = canonical_token_map.get(raw_tokens)
        if canonical is None:
            for candidate_tokens in ordered_nhtsa:
                if len(raw_tokens) <= len(candidate_tokens):
                    continue
                if raw_tokens[: len(candidate_tokens)] != candidate_tokens:
                    continue
                suffix = set(raw_tokens[len(candidate_tokens) :])
                if suffix and suffix.issubset(_SOURCE_MODEL_SUFFIX_TOKENS):
                    canonical = canonical_token_map[candidate_tokens]
                    break
        if canonical is None:
            key = normalized_key(label)
            canonical = next(
                (name for name in inventory if normalized_key(name) == key),
                label,
            )
        inventory.setdefault(canonical, {}).setdefault("fueleconomy_gov", []).append(label)

    for provider_map in inventory.values():
        for provider, labels in provider_map.items():
            provider_map[provider] = sorted(dict.fromkeys(labels), key=str.casefold)
    return inventory


def model_variant(canonical_model: str, source_model: str) -> str | None:
    base = _tokens(canonical_model)
    source = _tokens(source_model)
    if source == base + ("hybrid",):
        return "Hybrid"
    return None


def combine_trim_variant(trim: str | None, variant: str | None) -> str | None:
    if variant is None:
        return trim
    if trim is None or normalized_key(trim) in {"base", "standard"}:
        return variant
    if normalized_key(variant) in set(_tokens(trim)):
        return trim
    return f"{trim} {variant}"


def trim_from_kbb_style(style: str) -> str | None:
    value = _SPACE_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", style))).strip(" -|\t\r\n")
    if not value:
        return None
    value = re.sub(r"\s+\dD$", "", value, flags=re.I).strip()
    value = _KBB_BODY_SUFFIX_RE.sub("", value).strip()
    value = re.sub(r"\s+\dD$", "", value, flags=re.I).strip()
    if not value or normalized_key(value) in _KBB_EXCLUDED_STYLE_KEYS:
        return None
    if len(value) > 100:
        return None
    return value


def extract_kbb_trims(raw: bytes, make: str, model: str, year: int) -> list[str]:
    text = raw.decode("utf-8", errors="replace")
    make_slug = re.escape(slug(make))
    model_slug = re.escape(slug(model))
    path = rf"/{make_slug}/{model_slug}/{year}/([^/?#\"']+)/?"
    anchor_pattern = re.compile(
        rf"<a\b[^>]*href=[\"'](?:https://www\.kbb\.com)?{path}[^\"']*[\"']"
        rf"[^>]*>(.*?)</a>",
        re.I | re.S,
    )
    trims: dict[str, str] = {}
    for match in anchor_pattern.finditer(text):
        style_slug = normalized_key(match.group(1).replace("-", " "))
        if style_slug in _KBB_EXCLUDED_STYLE_KEYS:
            continue
        trim = trim_from_kbb_style(match.group(2))
        if trim is None:
            continue
        trims.setdefault(normalized_key(trim), trim)

    visible = _SPACE_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", text)))
    mpg_pattern = re.compile(
        rf"{year}\s+{re.escape(model)}\s+(.{{1,100}}?)\s+-\s+city\s+\d+\s+MPG",
        re.I,
    )
    for match in mpg_pattern.finditer(visible):
        trim = trim_from_kbb_style(match.group(1))
        if trim is not None:
            trims.setdefault(normalized_key(trim), trim)
    return sorted(trims.values(), key=str.casefold)


def trim_from_carsdirect_style(style: str) -> str | None:
    value = _SPACE_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", style))).strip(" -|\t\r\n")
    if not value:
        return None
    break_match = _CARSDIRECT_STYLE_BREAK_RE.search(value)
    if break_match is None:
        return None
    value = value[: break_match.start()].strip()
    if not value or normalized_key(value) in _CARSDIRECT_EXCLUDED_KEYS:
        return None
    if len(value) > 100:
        return None
    return value


def extract_carsdirect_trims(raw: bytes, model: str, year: int) -> list[str]:
    text = raw.decode("utf-8", errors="replace")
    trims: dict[str, str] = {}

    for option in re.findall(r"<option\b[^>]*>(.*?)</option>", text, re.I | re.S):
        trim = trim_from_carsdirect_style(option)
        if trim is not None:
            trims.setdefault(normalized_key(trim), trim)

    visible = _SPACE_RE.sub(" ", html.unescape(_TAG_RE.sub(" ", text)))
    marker = "Select a Trim"
    marker_index = visible.casefold().find(marker.casefold())
    if marker_index >= 0:
        segment = visible[marker_index : marker_index + 6000]
        style_pattern = re.compile(
            r"(?<![A-Za-z0-9-])"
            r"([A-Za-z0-9][A-Za-z0-9+./&' -]{0,70}?)\s+"
            r"(?:[2-5]dr|2-door|3-door|4-door|5-door)\s+"
            r"(?:[A-Za-z-]+\s+){0,5}"
            r"(?:Sedan|Coupe|Hatchback|Wagon|SUV|Convertible|Roadster|Van|Pickup)",
            re.I,
        )
        for match in style_pattern.finditer(segment):
            trim = trim_from_carsdirect_style(match.group(0))
            if trim is not None:
                trims.setdefault(normalized_key(trim), trim)

    fallback = re.compile(
        rf"{year}\s+[^\n]{{0,80}}?{re.escape(model)}\s+"
        r"([A-Za-z0-9][A-Za-z0-9+./&' -]{0,70}?)\s+"
        r"(?:[2-5]dr|2-door|3-door|4-door|5-door)\s+"
        r"(?:Sedan|Coupe|Hatchback|Wagon|SUV|Convertible|Roadster|Van|Pickup)",
        re.I,
    )
    for match in fallback.finditer(visible):
        trim = trim_from_carsdirect_style(match.group(1))
        if trim is not None:
            trims.setdefault(normalized_key(trim), trim)
    return sorted(trims.values(), key=str.casefold)


def _cache_path(provider: str, make: str, year: int, url: str, suffix: str) -> Path:
    url_hash = sha256(url.encode()).hexdigest()
    return (
        Path(settings.workbench_cache_root)
        / "identity"
        / slug(make)
        / str(year)
        / provider
        / f"{url_hash}.{suffix}"
    )


def _fetch_cached(
    provider: str,
    make: str,
    year: int,
    url: str,
    *,
    accept: str,
    suffix: str,
    refresh: bool,
) -> tuple[bytes | None, dict[str, object]]:
    path = _cache_path(provider, make, year, url, suffix)
    if path.exists() and not refresh:
        raw = path.read_bytes()
        return raw, {
            "status": "cached",
            "url": url,
            "cache_path": str(path.relative_to(Path(settings.workbench_cache_root))),
            "sha256": sha256(raw).hexdigest(),
        }

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.8",
        },
    )
    try:
        with urlopen(
            request,
            timeout=settings.workbench_fetch_timeout_seconds,
        ) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError("identity source response exceeded 8 MiB limit")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            return raw, {
                "status": "success",
                "http_status": int(getattr(response, "status", 200)),
                "url": url,
                "cache_path": str(path.relative_to(Path(settings.workbench_cache_root))),
                "sha256": sha256(raw).hexdigest(),
            }
    except HTTPError as exc:
        return None, {
            "status": (
                "not_found"
                if exc.code == 404
                else "blocked"
                if exc.code == 403
                else "failed"
            ),
            "http_status": exc.code,
            "url": url,
            "error": str(exc)[:300],
        }
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        return None, {"status": "failed", "url": url, "error": str(exc)[:300]}


def _nhtsa_models(make: str, year: int, refresh: bool) -> tuple[list[str], dict[str, object]]:
    url = (
        f"{settings.nhtsa_base_url}/GetModelsForMakeYear/make/{quote(make)}/"
        f"modelyear/{year}?format=json"
    )
    raw, evidence = _fetch_cached(
        "nhtsa_vpic",
        make,
        year,
        url,
        accept="application/json",
        suffix="json",
        refresh=refresh,
    )
    if raw is None:
        return [], evidence
    try:
        payload = json.loads(raw)
        results = payload.get("Results", []) if isinstance(payload, dict) else []
        models = [
            str(item.get("Model_Name", "")).strip()
            for item in results
            if isinstance(item, dict) and item.get("Model_Name")
        ]
        return sorted(dict.fromkeys(models), key=str.casefold), evidence
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        evidence["status"] = "failed"
        evidence["error"] = f"invalid NHTSA payload: {exc}"[:300]
        return [], evidence


def _fueleconomy_models(
    make: str,
    year: int,
    refresh: bool,
) -> tuple[list[str], dict[str, object]]:
    query = urlencode({"year": year, "make": make})
    url = f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/model?{query}"
    raw, evidence = _fetch_cached(
        "fueleconomy_gov",
        make,
        year,
        url,
        accept="application/xml,text/xml;q=0.9",
        suffix="xml",
        refresh=refresh,
    )
    if raw is None:
        return [], evidence
    try:
        text = raw.decode("utf-8", errors="replace")
        values = re.findall(r"<value>(.*?)</value>", text, re.I | re.S)
        models = [_SPACE_RE.sub(" ", html.unescape(value)).strip() for value in values]
        return sorted(dict.fromkeys(filter(None, models)), key=str.casefold), evidence
    except (TypeError, ValueError) as exc:
        evidence["status"] = "failed"
        evidence["error"] = f"invalid FuelEconomy payload: {exc}"[:300]
        return [], evidence


def _kbb_trims(
    make: str,
    source_model: str,
    year: int,
    refresh: bool,
) -> tuple[list[str], dict[str, object]]:
    url = f"https://www.kbb.com/{slug(make)}/{slug(source_model)}/{year}/"
    raw, evidence = _fetch_cached(
        "kbb",
        make,
        year,
        url,
        accept="text/html,application/xhtml+xml;q=0.9",
        suffix="html",
        refresh=refresh,
    )
    if raw is None:
        return [], evidence
    return extract_kbb_trims(raw, make, source_model, year), evidence


def _carsdirect_trims(
    make: str,
    source_model: str,
    year: int,
    refresh: bool,
) -> tuple[list[str], dict[str, object]]:
    url = f"https://www.carsdirect.com/{slug(make)}/{slug(source_model)}/{year}/specs"
    raw, evidence = _fetch_cached(
        "carsdirect",
        make,
        year,
        url,
        accept="text/html,application/xhtml+xml;q=0.9",
        suffix="html",
        refresh=refresh,
    )
    if raw is None:
        return [], evidence
    return extract_carsdirect_trims(raw, source_model, year), evidence


def _source_model_aliases(
    canonical_model: str,
    provider_labels: dict[str, list[str]],
) -> list[str]:
    labels = [canonical_model]
    base_tokens = _tokens(canonical_model)
    for provider_values in provider_labels.values():
        for value in provider_values:
            if _tokens(value) == base_tokens or model_variant(canonical_model, value) is not None:
                labels.append(value)
    return sorted(
        dict.fromkeys(labels),
        key=lambda value: (value != canonical_model, value.casefold()),
    )


async def _upsert_model(
    make: str,
    year: int,
    model: str,
    source_labels: dict[str, list[str]],
    source_evidence: dict[str, dict[str, object]],
) -> CatalogIdentityModel:
    make_key = normalized_key(make)
    model_key = normalized_key(model)
    sources = {
        provider: {
            "labels": labels,
            "capture": source_evidence.get(provider),
        }
        for provider, labels in source_labels.items()
    }
    async with session_factory() as session:
        async with session.begin():
            row = await session.scalar(
                select(CatalogIdentityModel).where(
                    CatalogIdentityModel.market == US_IDENTITY_MARKET,
                    CatalogIdentityModel.year == year,
                    CatalogIdentityModel.make_key == make_key,
                    CatalogIdentityModel.model_key == model_key,
                )
            )
            if row is None:
                row = CatalogIdentityModel(
                    market=US_IDENTITY_MARKET,
                    year=year,
                    make=make,
                    make_key=make_key,
                    model=model,
                    model_key=model_key,
                    sources=sources,
                    source_count=len(sources),
                    status="corroborated" if len(sources) >= 2 else "discovered",
                )
                session.add(row)
                await session.flush()
            else:
                merged = dict(row.sources)
                merged.update(sources)
                row.make = make
                row.model = model
                row.sources = merged
                row.source_count = len(merged)
                row.status = "corroborated" if len(merged) >= 2 else "discovered"
            return row


async def _upsert_trim(
    model_row: CatalogIdentityModel,
    trim: str,
    provider: str,
    evidence: dict[str, object],
) -> None:
    trim_key = normalized_key(trim)
    if not trim_key:
        return
    async with session_factory() as session:
        async with session.begin():
            row = await session.scalar(
                select(CatalogIdentityTrim).where(
                    CatalogIdentityTrim.model_id == model_row.id,
                    CatalogIdentityTrim.trim_key == trim_key,
                )
            )
            source_payload = {provider: evidence}
            if row is None:
                session.add(
                    CatalogIdentityTrim(
                        model_id=model_row.id,
                        trim=trim,
                        trim_key=trim_key,
                        status="discovered",
                        source_count=1,
                        sources=source_payload,
                    )
                )
            else:
                merged = dict(row.sources)
                merged.update(source_payload)
                row.trim = trim
                row.sources = merged
                row.source_count = len(merged)
                row.status = "corroborated" if len(merged) >= 2 else "discovered"


async def _progress(make: str, year: int) -> CatalogIdentityProgress:
    async with session_factory() as session:
        async with session.begin():
            row = await session.scalar(
                select(CatalogIdentityProgress).where(
                    CatalogIdentityProgress.make == make,
                    CatalogIdentityProgress.year == year,
                )
            )
            if row is None:
                row = CatalogIdentityProgress(make=make, year=year, status="pending")
                session.add(row)
                await session.flush()
            return row


async def _collect_trim_source(
    model_row: CatalogIdentityModel,
    canonical_model: str,
    source_model: str,
    provider: str,
    trims: list[str],
    evidence: dict[str, object],
) -> int:
    variant = model_variant(canonical_model, source_model)
    canonical_trims = {
        combined
        for trim in trims
        if (combined := combine_trim_variant(trim, variant)) is not None
    }
    if variant is not None and not canonical_trims and evidence.get("status") in {
        "success",
        "cached",
    }:
        canonical_trims.add(variant)

    enriched_evidence = dict(evidence)
    enriched_evidence["source_model"] = source_model
    if variant is not None:
        enriched_evidence["model_variant"] = variant
    for trim in sorted(canonical_trims, key=str.casefold):
        await _upsert_trim(model_row, trim, provider, enriched_evidence)
    return len(canonical_trims)


async def collect_make_year(make: str, year: int, *, refresh: bool) -> None:
    progress = await _progress(make, year)
    if progress.status == "completed" and not refresh:
        print(f"SKIP {year} {make}: already completed")
        return

    async with session_factory() as session:
        async with session.begin():
            row = await session.get(CatalogIdentityProgress, progress.id)
            if row is None:
                return
            row.status = "running"
            row.started_at = _now()
            row.completed_at = None
            row.last_error = None

    try:
        nhtsa_models, nhtsa_evidence = await asyncio.to_thread(
            _nhtsa_models, make, year, refresh
        )
        fueleconomy_models, fueleconomy_evidence = await asyncio.to_thread(
            _fueleconomy_models, make, year, refresh
        )
        inventory = canonicalize_model_inventory(nhtsa_models, fueleconomy_models)
        source_evidence = {
            "nhtsa_vpic": nhtsa_evidence,
            "fueleconomy_gov": fueleconomy_evidence,
        }

        if refresh and inventory:
            async with session_factory() as session:
                async with session.begin():
                    await session.execute(
                        delete(CatalogIdentityModel).where(
                            CatalogIdentityModel.market == US_IDENTITY_MARKET,
                            CatalogIdentityModel.year == year,
                            CatalogIdentityModel.make_key == normalized_key(make),
                        )
                    )

        unique_trim_keys: set[tuple[str, str]] = set()
        summaries = {
            "kbb": {"success": 0, "not_found": 0, "blocked": 0, "failed": 0},
            "carsdirect": {"success": 0, "not_found": 0, "blocked": 0, "failed": 0},
        }
        for model, provider_labels in sorted(inventory.items(), key=lambda item: item[0].casefold()):
            model_row = await _upsert_model(
                make,
                year,
                model,
                provider_labels,
                source_evidence,
            )
            for source_model in _source_model_aliases(model, provider_labels):
                for provider, fetcher in (
                    ("kbb", _kbb_trims),
                    ("carsdirect", _carsdirect_trims),
                ):
                    trims, evidence = await asyncio.to_thread(
                        fetcher, make, source_model, year, refresh
                    )
                    status = str(evidence.get("status", "failed"))
                    summary_key = "success" if status in {"success", "cached"} else status
                    provider_summary = summaries[provider]
                    if summary_key in provider_summary:
                        provider_summary[summary_key] += 1
                    variant = model_variant(model, source_model)
                    canonical_trims = {
                        combined
                        for trim in trims
                        if (combined := combine_trim_variant(trim, variant)) is not None
                    }
                    if variant is not None and not canonical_trims and status in {
                        "success",
                        "cached",
                    }:
                        canonical_trims.add(variant)
                    await _collect_trim_source(
                        model_row,
                        model,
                        source_model,
                        provider,
                        trims,
                        evidence,
                    )
                    for trim in canonical_trims:
                        unique_trim_keys.add((normalized_key(model), normalized_key(trim)))

        async with session_factory() as session:
            async with session.begin():
                row = await session.get(CatalogIdentityProgress, progress.id)
                if row is None:
                    return
                row.status = "completed"
                row.models_found = len(inventory)
                row.trims_found = len(unique_trim_keys)
                row.source_summary = {
                    "nhtsa_vpic": nhtsa_evidence,
                    "fueleconomy_gov": fueleconomy_evidence,
                    **summaries,
                }
                row.completed_at = _now()
        print(
            f"PASS {year} {make}: {len(inventory)} models, "
            f"{len(unique_trim_keys)} canonical model-trim rows"
        )
    except Exception as exc:
        async with session_factory() as session:
            async with session.begin():
                row = await session.get(CatalogIdentityProgress, progress.id)
                if row is not None:
                    row.status = "failed"
                    row.last_error = str(exc)[:2000]
        print(f"FAIL {year} {make}: {exc}")


async def collect_scope(
    makes: tuple[str, ...],
    year_from: int,
    year_to: int,
    *,
    refresh: bool,
) -> None:
    for make in makes:
        for year in range(year_from, year_to + 1):
            await collect_make_year(make, year, refresh=refresh)


async def print_status() -> None:
    async with session_factory() as session:
        for make in US_IDENTITY_MAKES:
            completed = int(
                await session.scalar(
                    select(func.count(CatalogIdentityProgress.id)).where(
                        CatalogIdentityProgress.make == make,
                        CatalogIdentityProgress.status == "completed",
                    )
                )
                or 0
            )
            failed = int(
                await session.scalar(
                    select(func.count(CatalogIdentityProgress.id)).where(
                        CatalogIdentityProgress.make == make,
                        CatalogIdentityProgress.status == "failed",
                    )
                )
                or 0
            )
            models = int(
                await session.scalar(
                    select(func.count(CatalogIdentityModel.id)).where(
                        CatalogIdentityModel.make_key == normalized_key(make)
                    )
                )
                or 0
            )
            trims = int(
                await session.scalar(
                    select(func.count(CatalogIdentityTrim.id))
                    .join(CatalogIdentityModel)
                    .where(CatalogIdentityModel.make_key == normalized_key(make))
                )
                or 0
            )
            print(
                f"{make:<8} years={completed:>2}/32 failed={failed:>2} "
                f"model-years={models:>4} trims={trims:>5}"
            )


async def export_json(path: str) -> None:
    async with session_factory() as session:
        models = list(
            await session.scalars(
                select(CatalogIdentityModel).order_by(
                    CatalogIdentityModel.make,
                    CatalogIdentityModel.year,
                    CatalogIdentityModel.model,
                )
            )
        )
        trims = list(
            await session.scalars(
                select(CatalogIdentityTrim).order_by(CatalogIdentityTrim.trim)
            )
        )
    trims_by_model: dict[str, list[CatalogIdentityTrim]] = {}
    for trim in trims:
        trims_by_model.setdefault(str(trim.model_id), []).append(trim)

    payload: dict[str, object] = {
        "scope": {
            "market": US_IDENTITY_MARKET,
            "year_from": US_IDENTITY_YEAR_MIN,
            "year_to": US_IDENTITY_YEAR_MAX,
            "makes": list(US_IDENTITY_MAKES),
        },
        "generated_at": _now().isoformat(),
        "models": [
            {
                "year": model.year,
                "make": model.make,
                "model": model.model,
                "status": model.status,
                "source_count": model.source_count,
                "sources": model.sources,
                "trims": [
                    {
                        "trim": trim.trim,
                        "status": trim.status,
                        "source_count": trim.source_count,
                        "sources": trim.sources,
                    }
                    for trim in trims_by_model.get(str(model.id), [])
                ],
            }
            for model in models
        ],
    }
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, sort_keys=False), encoding="utf-8")
    print(f"Exported {len(models)} model-year rows to {destination}")


def _parse_makes(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return US_IDENTITY_MAKES
    result: list[str] = []
    for value in values:
        make = canonical_scoped_make(value)
        if make is None:
            allowed = ", ".join(US_IDENTITY_MAKES)
            raise ValueError(f"make {value!r} is outside the active scope: {allowed}")
        if make not in result:
            result.append(make)
    return tuple(result)


async def _main_async(args: argparse.Namespace) -> None:
    if args.status:
        await print_status()
        return
    if args.export_json:
        await export_json(args.export_json)
        return
    makes = _parse_makes(args.make)
    if not US_IDENTITY_YEAR_MIN <= args.year_from <= US_IDENTITY_YEAR_MAX:
        raise ValueError("year-from is outside the active identity scope")
    if not US_IDENTITY_YEAR_MIN <= args.year_to <= US_IDENTITY_YEAR_MAX:
        raise ValueError("year-to is outside the active identity scope")
    if args.year_from > args.year_to:
        raise ValueError("year-from must be less than or equal to year-to")
    await collect_scope(makes, args.year_from, args.year_to, refresh=args.refresh)


async def _run(args: argparse.Namespace) -> None:
    try:
        await _main_async(args)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect US make/model/trim inventory before technical specifications"
    )
    parser.add_argument("--make", action="append", help="repeat for one or more scoped makes")
    parser.add_argument("--year-from", type=int, default=US_IDENTITY_YEAR_MIN)
    parser.add_argument("--year-to", type=int, default=US_IDENTITY_YEAR_MAX)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--export-json")
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
