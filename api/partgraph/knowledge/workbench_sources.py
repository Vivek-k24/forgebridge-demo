from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from ..config import settings
from ..identity.vehicle.models import VehicleConfiguration

USER_AGENT = (
    "Mozilla/5.0 (compatible; PartGraphResearch/1.0; "
    "+local-operator-controlled-catalog-workbench)"
)
TAG_RE = re.compile(r"<[^>]+>")
SPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class SourceFetchResult:
    provider: str
    source_url: str
    fetch_status: str
    http_status: int | None
    matched_fields: dict[str, object]
    raw_sha256: str | None
    cache_path: str | None
    error: str | None
    raw_metadata: dict[str, object]


def _reference_model(configuration: VehicleConfiguration) -> str:
    make = configuration.make
    model = configuration.model
    trim = configuration.trim or ""
    if make == "Lexus":
        if model == "ES":
            return "ES 300"
        if model == "GS":
            return "GS 400" if "GS 400" in trim else "GS 300"
        if model == "LS":
            return "LS 400"
    if make == "Subaru" and model == "OUTBACK" and configuration.year <= 1999:
        return "Legacy Outback"
    return model


def _slug(value: str, separator: str = "-") -> str:
    tokens = TOKEN_RE.findall(value.casefold())
    return separator.join(tokens)


def source_requests(configuration: VehicleConfiguration) -> tuple[tuple[str, str], ...]:
    make = configuration.make
    model = _reference_model(configuration)
    year = configuration.year
    make_slug = _slug(make)
    model_slug = _slug(model)
    cars_model = _slug(model, "_")
    nhtsa = (
        f"{settings.nhtsa_base_url}/GetModelsForMakeYear/make/{quote(make)}/"
        f"modelyear/{year}?format=json"
    )
    return (
        ("nhtsa_vpic", nhtsa),
        ("cars_com", f"https://www.cars.com/research/{make_slug}-{cars_model}-{year}/trims/"),
        ("edmunds", f"https://www.edmunds.com/{make_slug}/{model_slug}/{year}/features-specs/"),
        ("kbb", f"https://www.kbb.com/{make_slug}/{model_slug}/{year}/"),
        ("motortrend", f"https://www.motortrend.com/cars/{make_slug}/{model_slug}/{year}/"),
    )


def _visible_text(raw: bytes, content_type: str) -> str:
    decoded = raw.decode("utf-8", errors="replace")
    if "json" in content_type.casefold():
        try:
            decoded = json.dumps(json.loads(decoded), ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    else:
        decoded = TAG_RE.sub(" ", decoded)
        decoded = html.unescape(decoded)
    return SPACE_RE.sub(" ", decoded).casefold()


def _tokens(value: str | None, *, ignore: set[str] | None = None) -> list[str]:
    if not value:
        return []
    ignored = ignore or set()
    return [token for token in TOKEN_RE.findall(value.casefold()) if token not in ignored]


def _all_tokens(text: str, value: str | None, *, ignore: set[str] | None = None) -> bool:
    tokens = _tokens(value, ignore=ignore)
    return not tokens or all(token in text for token in tokens)


def _engine_signature(text: str, engine: str | None) -> bool:
    if not engine:
        return True
    value = engine.casefold()
    displacement = re.search(r"(\d+(?:\.\d+)?)\s*l\b", value)
    if displacement and displacement.group(1) not in text:
        return False
    required_groups: list[tuple[str, ...]] = []
    if "v8" in value:
        required_groups.append(("v8", "8 cylinder", "8-cylinder"))
    elif "v6" in value:
        required_groups.append(("v6", "6 cylinder", "6-cylinder"))
    elif "flat-4" in value or "flat 4" in value:
        required_groups.append(("flat 4", "flat-4", "h4", "4 cylinder", "4-cylinder"))
    elif "inline-6" in value or "inline 6" in value:
        required_groups.append(("inline 6", "inline-6", "i6", "6 cylinder", "6-cylinder"))
    elif "4-cyl" in value or "4 cyl" in value or "i4" in value:
        required_groups.append(("i4", "4 cyl", "4-cyl", "4 cylinder", "4-cylinder"))
    if "vtec" in value:
        required_groups.append(("vtec",))
    return all(any(token in text for token in group) for group in required_groups)


def _transmission_signature(text: str, transmission: str | None) -> bool:
    if not transmission:
        return True
    value = transmission.casefold()
    if "cvt" in value and "cvt" not in text and "continuously variable" not in text:
        return False
    if "manual" in value and "manual" not in text:
        return False
    if "automatic" in value and "automatic" not in text and "auto" not in text:
        return False
    speed = re.search(r"\b([3-9])\s*-?\s*speed\b", value)
    if speed:
        number = speed.group(1)
        if not re.search(rf"\b{number}\s*-?\s*speed\b", text):
            return False
    return True


def _matching_window(text: str, configuration: VehicleConfiguration) -> str:
    trim = configuration.trim or ""
    ignored = {"base"} | set(_tokens(configuration.make)) | set(_tokens(configuration.model))
    trim_tokens = _tokens(trim, ignore=ignored)
    anchors = trim_tokens or _tokens(_reference_model(configuration))
    for anchor in anchors:
        position = text.find(anchor)
        if position >= 0:
            start = max(0, position - 2500)
            end = min(len(text), position + 5000)
            return text[start:end]
    return text[:7500]


def match_source(
    provider: str,
    raw: bytes,
    content_type: str,
    configuration: VehicleConfiguration,
) -> dict[str, object]:
    text = _visible_text(raw, content_type)
    reference_model = _reference_model(configuration)
    make_match = _all_tokens(text, configuration.make)
    model_match = _all_tokens(text, reference_model) or _all_tokens(text, configuration.model)
    year_match = str(configuration.year) in text

    if provider == "nhtsa_vpic":
        try:
            payload = json.loads(raw.decode("utf-8", errors="replace"))
            model_names = {
                str(item.get("Model_Name", "")).casefold()
                for item in payload.get("Results", [])
                if isinstance(item, dict)
            }
            model_match = (
                configuration.model.casefold() in model_names
                or reference_model.casefold() in model_names
                or any(configuration.model.casefold() in value for value in model_names)
            )
            make_match = True
            year_match = True
        except (json.JSONDecodeError, AttributeError):
            pass
        return {
            "year": year_match,
            "make": make_match,
            "model": model_match,
            "trim": False,
            "engine": False,
            "transmission": False,
            "configuration_match": False,
            "reference_model": reference_model,
        }

    window = _matching_window(text, configuration)
    ignored_trim_tokens = (
        {"base"}
        | set(_tokens(configuration.make))
        | set(_tokens(configuration.model))
        | set(_tokens(reference_model))
    )
    trim_match = _all_tokens(window, configuration.trim, ignore=ignored_trim_tokens)
    engine_match = _engine_signature(window, configuration.engine)
    transmission_match = _transmission_signature(window, configuration.transmission)
    configuration_match = (
        year_match
        and make_match
        and model_match
        and trim_match
        and engine_match
        and transmission_match
    )
    return {
        "year": year_match,
        "make": make_match,
        "model": model_match,
        "trim": trim_match,
        "engine": engine_match,
        "transmission": transmission_match,
        "configuration_match": configuration_match,
        "reference_model": reference_model,
    }


def fetch_source(
    provider: str,
    source_url: str,
    configuration: VehicleConfiguration,
) -> SourceFetchResult:
    request = Request(
        source_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.7",
            "Accept-Language": "en-US,en;q=0.8",
        },
    )
    try:
        with urlopen(request, timeout=settings.workbench_fetch_timeout_seconds) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError("source response exceeded 8 MiB workbench limit")
            content_type = response.headers.get("Content-Type", "application/octet-stream")
            http_status = getattr(response, "status", 200)
    except HTTPError as exc:
        status = int(exc.code)
        fetch_status = "not_found" if status == 404 else ("blocked" if status in {401, 403, 429} else "failed")
        return SourceFetchResult(
            provider=provider,
            source_url=source_url,
            fetch_status=fetch_status,
            http_status=status,
            matched_fields={},
            raw_sha256=None,
            cache_path=None,
            error=f"HTTP {status}",
            raw_metadata={},
        )
    except (URLError, TimeoutError, ValueError, OSError) as exc:
        return SourceFetchResult(
            provider=provider,
            source_url=source_url,
            fetch_status="failed",
            http_status=None,
            matched_fields={},
            raw_sha256=None,
            cache_path=None,
            error=str(exc)[:500],
            raw_metadata={},
        )

    digest = sha256(raw).hexdigest()
    suffix = ".json" if "json" in content_type.casefold() else ".html"
    cache_root = Path(settings.workbench_cache_root)
    relative = Path(configuration.make) / str(configuration.year) / provider / f"{digest}{suffix}"
    destination = cache_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw)
    matched_fields = match_source(provider, raw, content_type, configuration)
    return SourceFetchResult(
        provider=provider,
        source_url=source_url,
        fetch_status="success",
        http_status=http_status,
        matched_fields=matched_fields,
        raw_sha256=digest,
        cache_path=str(relative),
        error=None,
        raw_metadata={
            "content_type": content_type,
            "bytes": len(raw),
        },
    )
