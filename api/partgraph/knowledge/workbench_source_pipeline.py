from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from ..config import settings
from ..identity.vehicle.models import VehicleConfiguration
from ..identity.vehicle.specification_taxonomy import (
    core_configuration_fields,
    normalize_observation_value,
    seed_profile_fields,
    split_engine_descriptor,
    split_transmission_descriptor,
)

USER_AGENT = (
    "Mozilla/5.0 (compatible; PartGraphResearch/2.0; "
    "+local-operator-controlled-catalog-workbench)"
)
EXTRACTION_METHOD = "local_field_observation_v2"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class SourceRequest:
    source_key: str
    source_class: str
    source_url: str


@dataclass(frozen=True, slots=True)
class SourceExtraction:
    matched_fields: dict[str, object]
    field_observations: dict[str, dict[str, object]]


@dataclass(frozen=True, slots=True)
class SourceFetchResult:
    provider: str
    source_class: str
    source_url: str
    fetch_status: str
    http_status: int | None
    matched_fields: dict[str, object]
    field_observations: dict[str, dict[str, object]]
    raw_sha256: str | None
    cache_path: str | None
    error: str | None
    raw_metadata: dict[str, object]


def _reference_model(configuration: VehicleConfiguration) -> str:
    trim = configuration.trim or ""
    if configuration.make == "Lexus":
        if configuration.model == "ES":
            return "ES 300"
        if configuration.model == "GS":
            return "GS 400" if "GS 400" in trim else "GS 300"
        if configuration.model == "LS":
            return "LS 400"
    if (
        configuration.make == "Subaru"
        and configuration.model == "OUTBACK"
        and configuration.year <= 1999
    ):
        return "Legacy Outback"
    return configuration.model


def _slug(value: str, separator: str = "-") -> str:
    return separator.join(_TOKEN_RE.findall(value.casefold()))


def _nhtsa(configuration: VehicleConfiguration) -> SourceRequest:
    url = (
        f"{settings.nhtsa_base_url}/GetModelsForMakeYear/make/{quote(configuration.make)}/"
        f"modelyear/{configuration.year}?format=json"
    )
    return SourceRequest("nhtsa_vpic", "government", url)


def _fueleconomy(configuration: VehicleConfiguration) -> SourceRequest:
    query = urlencode(
        {
            "year": configuration.year,
            "make": configuration.make,
            "model": _reference_model(configuration),
        }
    )
    return SourceRequest(
        "fueleconomy_gov",
        "government",
        f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/options?{query}",
    )


def _cars(configuration: VehicleConfiguration) -> SourceRequest:
    return SourceRequest(
        "cars_com",
        "vehicle_reference",
        (
            f"https://www.cars.com/research/{_slug(configuration.make)}-"
            f"{_slug(_reference_model(configuration), '_')}-{configuration.year}/trims/"
        ),
    )


def _edmunds(configuration: VehicleConfiguration) -> SourceRequest:
    return SourceRequest(
        "edmunds",
        "vehicle_reference",
        (
            f"https://www.edmunds.com/{_slug(configuration.make)}/"
            f"{_slug(_reference_model(configuration))}/{configuration.year}/features-specs/"
        ),
    )


def _kbb(configuration: VehicleConfiguration) -> SourceRequest:
    return SourceRequest(
        "kbb",
        "vehicle_reference",
        (
            f"https://www.kbb.com/{_slug(configuration.make)}/"
            f"{_slug(_reference_model(configuration))}/{configuration.year}/"
        ),
    )


def _motortrend(configuration: VehicleConfiguration) -> SourceRequest:
    return SourceRequest(
        "motortrend",
        "vehicle_reference",
        (
            f"https://www.motortrend.com/cars/{_slug(configuration.make)}/"
            f"{_slug(_reference_model(configuration))}/{configuration.year}/"
        ),
    )


# This is an adapter registry, not an evidence ceiling. Add reviewed adapters
# without changing the reconciliation rule; ordinary fields still need three
# independent agreeing sources and conflicts may require any number of extras.
_SOURCE_BUILDERS: tuple[Callable[[VehicleConfiguration], SourceRequest], ...] = (
    _nhtsa,
    _fueleconomy,
    _cars,
    _edmunds,
    _kbb,
    _motortrend,
)


def source_requests(configuration: VehicleConfiguration) -> tuple[SourceRequest, ...]:
    requests = tuple(builder(configuration) for builder in _SOURCE_BUILDERS)
    keys = [item.source_key for item in requests]
    if len(keys) != len(set(keys)):
        raise RuntimeError("duplicate independent source key in workbench registry")
    return requests


def _visible_text(raw: bytes, content_type: str) -> str:
    text = raw.decode("utf-8", errors="replace")
    if "json" not in content_type.casefold():
        text = html.unescape(_TAG_RE.sub(" ", text))
    return _SPACE_RE.sub(" ", text).casefold()


def _tokens(value: str | None, *, ignore: set[str] | None = None) -> list[str]:
    if not value:
        return []
    ignored = ignore or set()
    return [token for token in _TOKEN_RE.findall(value.casefold()) if token not in ignored]


def _all_tokens(text: str, value: str | None, *, ignore: set[str] | None = None) -> bool:
    tokens = _tokens(value, ignore=ignore)
    return bool(tokens) and all(token in text for token in tokens)


def _trim_tokens(configuration: VehicleConfiguration) -> list[str]:
    ignored = (
        set(_tokens(configuration.make))
        | set(_tokens(configuration.model))
        | set(_tokens(_reference_model(configuration)))
    )
    return _tokens(configuration.trim, ignore=ignored)


def _matching_window(text: str, configuration: VehicleConfiguration) -> str:
    anchors = _trim_tokens(configuration) or _tokens(_reference_model(configuration))
    positions = [text.find(anchor) for anchor in anchors if text.find(anchor) >= 0]
    if not positions:
        return text[:9000]
    position = min(positions)
    return text[max(0, position - 1800) : min(len(text), position + 4200)]


def _observation(
    value: object,
    *,
    scope: str,
    raw_value: object | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {"value": value, "kind": "ordinary", "scope": scope}
    if raw_value is not None:
        result["raw_value"] = raw_value
    return result


def _number_in_text(text: str, number: int | float, units: tuple[str, ...]) -> bool:
    value = f"{float(number):g}"
    unit_pattern = "|".join(re.escape(unit) for unit in units)
    return bool(re.search(rf"(?<!\d){re.escape(value)}\s*(?:{unit_pattern})\b", text, re.I))


def _supports_expected(text: str, field: str, value: object) -> bool:
    if field.startswith("identity.") and field not in {"identity.drivetrain"}:
        return _all_tokens(text, str(value))
    if field == "identity.drivetrain":
        aliases = {
            "FWD": ("fwd", "front wheel drive", "front-wheel drive"),
            "RWD": ("rwd", "rear wheel drive", "rear-wheel drive"),
            "AWD": ("awd", "all wheel drive", "all-wheel drive"),
            "4WD": ("4wd", "four wheel drive", "four-wheel drive", "4x4"),
        }
        return any(alias in text for alias in aliases.get(str(value), (str(value).casefold(),)))
    if field == "powertrain.engine.displacement_l" and isinstance(value, (int, float)):
        if _number_in_text(text, value, ("l", "liter", "liters", "litre", "litres")):
            return True
        return _number_in_text(text, int(round(float(value) * 1000)), ("cc", "cm3", "cm³"))
    if field == "powertrain.engine.cylinders" and isinstance(value, (int, float)):
        count = int(value)
        return bool(
            re.search(rf"\b{count}\s*[\s-]*(?:cyl|cylinder|cylinders)\b", text, re.I)
            or re.search(rf"\b(?:i|v|h){count}\b", text, re.I)
        )
    if field == "powertrain.engine.architecture":
        aliases = {
            "I3": ("i3", "inline 3", "inline-3"),
            "I4": ("i4", "inline 4", "inline-4"),
            "I5": ("i5", "inline 5", "inline-5"),
            "I6": ("i6", "inline 6", "inline-6"),
            "H4": ("h4", "flat 4", "flat-4", "boxer 4"),
            "H6": ("h6", "flat 6", "flat-6", "boxer 6"),
            "V6": ("v6", "v-6"),
            "V8": ("v8", "v-8"),
        }
        return any(alias in text for alias in aliases.get(str(value), (str(value).casefold(),)))
    if field == "powertrain.engine.technology":
        values = value if isinstance(value, list) else [value]
        return all(_all_tokens(text, str(item)) for item in values)
    if field == "powertrain.engine.aspiration":
        marker = str(value).casefold()
        return "turbo" in text if "turbo" in marker else marker in text
    if field == "powertrain.electrification":
        aliases = {
            "Hybrid": ("hybrid",),
            "PHEV": ("phev", "plug-in hybrid", "plug in hybrid"),
            "EV": ("battery electric", "bev", "electric vehicle"),
        }
        return any(alias in text for alias in aliases.get(str(value), (str(value).casefold(),)))
    if field == "powertrain.engine.valvetrain":
        return str(value).casefold() in text
    if field == "powertrain.engine.valves" and isinstance(value, (int, float)):
        return bool(re.search(rf"\b{int(value)}\s*[\s-]*valves?\b", text, re.I))
    if field == "performance.horsepower_hp" and isinstance(value, (int, float)):
        return _number_in_text(text, value, ("hp", "horsepower", "bhp"))
    if field == "performance.torque_lb_ft" and isinstance(value, (int, float)):
        return _number_in_text(text, value, ("lb-ft", "lb ft", "ft-lb", "ft lb"))
    if field == "transmission.family":
        family = str(value).casefold()
        aliases = {
            "cvt": ("cvt", "continuously variable"),
            "ecvt": ("ecvt", "electronic cvt"),
            "dct": ("dct", "dual clutch", "dual-clutch"),
            "manual": ("manual",),
            "automatic": ("automatic",),
        }
        return any(alias in text for alias in aliases.get(family, (family,)))
    if field == "transmission.speeds" and isinstance(value, (int, float)):
        return bool(re.search(rf"\b{int(value)}\s*[\s-]*(?:speed|spd)\b", text, re.I))
    return _all_tokens(text, str(value))


def _labeled_number(
    text: str,
    labels: tuple[str, ...],
    units: tuple[str, ...],
    minimum: float,
    maximum: float,
) -> int | float | None:
    label = "|".join(re.escape(item) for item in labels)
    unit = "|".join(re.escape(item) for item in units)
    match = re.search(
        rf"(?:{label})[^0-9]{{0,35}}(\d+(?:\.\d+)?)\s*(?:{unit})\b",
        text,
        re.I,
    )
    if not match:
        return None
    number = float(match.group(1))
    if not minimum <= number <= maximum:
        return None
    return int(number) if number.is_integer() else round(number, 3)


def _extra_technical_fields(text: str) -> dict[str, object]:
    fields: dict[str, object] = {}
    specs = (
        ("performance.horsepower_hp", ("horsepower",), ("hp", "bhp"), 20, 2000),
        ("performance.torque_lb_ft", ("torque",), ("lb-ft", "lb ft", "ft-lb"), 20, 3000),
        ("efficiency.epa_city_mpg", ("city mpg", "city",), ("mpg",), 5, 250),
        ("efficiency.epa_highway_mpg", ("highway mpg", "highway", "hwy"), ("mpg",), 5, 300),
        ("efficiency.epa_combined_mpg", ("combined mpg", "combined"), ("mpg",), 5, 300),
        ("dimensions_weight.wheelbase_in", ("wheelbase",), ("in", "inches"), 50, 200),
        ("dimensions_weight.length_in", ("overall length", "length"), ("in", "inches"), 80, 350),
        ("dimensions_weight.width_in", ("overall width", "width"), ("in", "inches"), 40, 150),
        ("dimensions_weight.height_in", ("overall height", "height"), ("in", "inches"), 30, 150),
        (
            "dimensions_weight.curb_weight_lb",
            ("curb weight",),
            ("lb", "lbs", "pounds"),
            1000,
            15000,
        ),
        (
            "capacity.fuel_tank_gallons",
            ("fuel tank", "fuel capacity"),
            ("gal", "gallons"),
            3,
            80,
        ),
        (
            "steering.turning_diameter_ft",
            ("turning diameter", "turning circle"),
            ("ft", "feet"),
            15,
            100,
        ),
    )
    for field, labels, units, minimum, maximum in specs:
        value = _labeled_number(text, labels, units, minimum, maximum)
        if value is not None:
            fields[field] = value

    tire = re.search(r"\b(?:p|lt)?\d{3}/\d{2,3}\s*r\s*\d{2}\b", text, re.I)
    if tire:
        fields["wheels_tires.tire_size"] = re.sub(r"\s+", "", tire.group(0)).upper()
    compression = re.search(
        r"compression ratio[^0-9]{0,25}(\d{1,2}(?:\.\d+)?)\s*:\s*1",
        text,
        re.I,
    )
    if compression:
        fields["powertrain.engine.compression_ratio"] = f"{compression.group(1)}:1"

    suspension = (
        ("MacPherson strut", ("macpherson strut", "macpherson")),
        ("Double wishbone", ("double wishbone", "double-wishbone")),
        ("Multi-link", ("multi-link", "multilink", "multi link")),
        ("Torsion beam", ("torsion beam", "torsion-beam")),
    )
    for end in ("front", "rear"):
        position = text.find(f"{end} suspension")
        if position >= 0:
            window = text[position : position + 160]
            for canonical, aliases in suspension:
                if any(alias in window for alias in aliases):
                    fields[f"suspension.{end}.type"] = canonical
                    break

    if "anti-lock" in text or "antilock" in text or re.search(r"\babs\b", text):
        fields["safety.abs"] = True
    if "traction control" in text:
        fields["safety.traction_control"] = True
    if "stability control" in text or "vehicle stability" in text:
        fields["safety.stability_control"] = True
    if "tire pressure monitoring" in text or "tpms" in text:
        fields["safety.tpms"] = True
    return fields


def _extract_html(
    raw: bytes,
    content_type: str,
    configuration: VehicleConfiguration,
) -> SourceExtraction:
    text = _visible_text(raw, content_type)
    reference_model = _reference_model(configuration)
    year_match = str(configuration.year) in text
    make_match = _all_tokens(text, configuration.make)
    model_match = _all_tokens(text, reference_model) or _all_tokens(text, configuration.model)
    identity_scope = year_match and make_match and model_match
    window = _matching_window(text, configuration)
    trim_tokens = _trim_tokens(configuration)
    trim_match = bool(trim_tokens) and all(token in window for token in trim_tokens)

    expected = seed_profile_fields(configuration)
    required = core_configuration_fields(configuration)
    supported = {
        field: _supports_expected(window, field, value)
        for field, value in expected.items()
        if not field.startswith("identity.")
    }
    observations: dict[str, dict[str, object]] = {}
    if identity_scope:
        for field in ("identity.year", "identity.make", "identity.model"):
            observations[field] = _observation(expected[field], scope="model_year")
    if identity_scope and configuration.trim and trim_match and "identity.trim" in expected:
        observations["identity.trim"] = _observation(expected["identity.trim"], scope="exact_trim")

    exact_scope = identity_scope and (trim_match if configuration.trim else True)
    if exact_scope:
        for field, value in expected.items():
            if field in observations or field in {
                "identity.year",
                "identity.make",
                "identity.model",
            }:
                continue
            if field.startswith("identity."):
                if _supports_expected(window, field, value):
                    observations[field] = _observation(value, scope="exact_configuration")
            elif supported.get(field):
                observations[field] = _observation(
                    normalize_observation_value(field, value),
                    scope="exact_configuration",
                )
        for field, value in _extra_technical_fields(window).items():
            observations.setdefault(
                field,
                _observation(
                    normalize_observation_value(field, value),
                    scope="exact_configuration",
                    raw_value=value,
                ),
            )

    full_seed_match = bool(required) and all(field in observations for field in required)
    engine_fields = list(split_engine_descriptor(configuration.engine))
    transmission_fields = list(split_transmission_descriptor(configuration.transmission))
    return SourceExtraction(
        matched_fields={
            "year": year_match,
            "make": make_match,
            "model": model_match,
            "trim": trim_match if configuration.trim else None,
            "engine": (
                all(field in observations for field in engine_fields)
                if engine_fields
                else None
            ),
            "transmission": (
                all(field in observations for field in transmission_fields)
                if transmission_fields
                else None
            ),
            "configuration_match": full_seed_match,
            "exact_configuration_scope": exact_scope,
            "reference_model": reference_model,
            "observed_fields": sorted(observations),
            "field_observations": observations,
        },
        field_observations=observations,
    )


def _extract_nhtsa(raw: bytes, configuration: VehicleConfiguration) -> SourceExtraction:
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        payload = {}
    reference_model = _reference_model(configuration)
    names = {
        str(item.get("Model_Name", "")).casefold()
        for item in payload.get("Results", [])
        if isinstance(item, dict)
    }
    matched = (
        configuration.model.casefold() in names
        or reference_model.casefold() in names
        or any(configuration.model.casefold() in name for name in names)
    )
    observations: dict[str, dict[str, object]] = {}
    if matched:
        observations = {
            "identity.year": _observation(configuration.year, scope="model_year"),
            "identity.make": _observation(configuration.make, scope="model_year"),
            "identity.model": _observation(configuration.model, scope="model_year"),
        }
    return SourceExtraction(
        matched_fields={
            "year": True,
            "make": True,
            "model": matched,
            "trim": None,
            "engine": None,
            "transmission": None,
            "configuration_match": False,
            "exact_configuration_scope": False,
            "reference_model": reference_model,
            "observed_fields": sorted(observations),
            "field_observations": observations,
        },
        field_observations=observations,
    )


def _xml_leaf_map(raw: bytes) -> dict[str, str]:
    root = ET.fromstring(raw)
    result: dict[str, str] = {}
    for node in root.iter():
        if len(node) == 0 and node.text and node.text.strip():
            result[node.tag.rsplit("}", 1)[-1]] = node.text.strip()
    return result


def _menu_ids(raw: bytes) -> list[str]:
    root = ET.fromstring(raw)
    return [
        value.text.strip()
        for value in root.findall(".//menuItem/value")
        if value.text and value.text.strip()
    ]


def _http(url: str, accept: str) -> tuple[bytes, str, int]:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.8",
        },
    )
    with urlopen(request, timeout=settings.workbench_fetch_timeout_seconds) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ValueError("source response exceeded 8 MiB workbench limit")
        return raw, response.headers.get("Content-Type", "application/octet-stream"), int(
            getattr(response, "status", 200)
        )


def _fueleconomy_bundle(url: str) -> tuple[bytes, str, int]:
    menu, _content_type, status = _http(url, "application/xml,text/xml;q=0.9")
    records: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    for vehicle_id in _menu_ids(menu):
        try:
            raw, _detail_type, _detail_status = _http(
                f"https://www.fueleconomy.gov/ws/rest/vehicle/{quote(vehicle_id)}",
                "application/xml,text/xml;q=0.9",
            )
            record = _xml_leaf_map(raw)
            record["_vehicle_id"] = vehicle_id
            records.append(record)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, ET.ParseError) as exc:
            errors.append({"vehicle_id": vehicle_id, "error": str(exc)[:300]})
    payload = {"records": records, "detail_errors": errors}
    return json.dumps(payload, separators=(",", ":")).encode(), "application/json", status


def _float(record: dict[str, str], key: str) -> float | None:
    try:
        return float(record[key])
    except (KeyError, TypeError, ValueError):
        return None


def _fueleconomy_fields(record: dict[str, str]) -> dict[str, object]:
    fields: dict[str, object] = {}
    if record.get("year"):
        fields["identity.year"] = int(record["year"])
    if record.get("make"):
        fields["identity.make"] = record["make"]
    if record.get("model"):
        fields["identity.model"] = record["model"]
    displacement = _float(record, "displ")
    cylinders = _float(record, "cylinders")
    if displacement is not None:
        fields["powertrain.engine.displacement_l"] = displacement
    if cylinders is not None:
        fields["powertrain.engine.cylinders"] = int(cylinders)
    if record.get("trany"):
        fields.update(split_transmission_descriptor(record["trany"]))
    drive = record.get("drive", "").casefold()
    if "front" in drive:
        fields["identity.drivetrain"] = "FWD"
    elif "rear" in drive:
        fields["identity.drivetrain"] = "RWD"
    elif "4-wheel" in drive or "4 wheel" in drive:
        fields["identity.drivetrain"] = "4WD"
    elif "all" in drive:
        fields["identity.drivetrain"] = "AWD"
    if record.get("fuelType1"):
        fields["powertrain.fuel_type"] = record["fuelType1"]
    for key, field in (
        ("city08", "efficiency.epa_city_mpg"),
        ("highway08", "efficiency.epa_highway_mpg"),
        ("comb08", "efficiency.epa_combined_mpg"),
    ):
        value = _float(record, key)
        if value is not None:
            fields[field] = int(value) if value.is_integer() else value
    if record.get("VClass"):
        fields["classification.epa_vehicle_class"] = record["VClass"]
    return fields


def _extract_fueleconomy(raw: bytes, configuration: VehicleConfiguration) -> SourceExtraction:
    try:
        payload = json.loads(raw.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        payload = {}
    expected = seed_profile_fields(configuration)
    reference_model = _reference_model(configuration)
    candidates: list[tuple[int, dict[str, object]]] = []
    for raw_record in payload.get("records", []):
        if not isinstance(raw_record, dict):
            continue
        record = {str(key): str(value) for key, value in raw_record.items()}
        fields = _fueleconomy_fields(record)
        if fields.get("identity.year") != configuration.year:
            continue
        if str(fields.get("identity.make", "")).casefold() != configuration.make.casefold():
            continue
        model_key = "".join(_tokens(str(fields.get("identity.model", ""))))
        model_candidates = {
            "".join(_tokens(configuration.model)),
            "".join(_tokens(reference_model)),
        }
        if not any(key and (key in model_key or model_key in key) for key in model_candidates):
            continue
        score = 10
        for field in (
            "powertrain.engine.displacement_l",
            "powertrain.engine.cylinders",
            "transmission.family",
            "transmission.speeds",
            "identity.drivetrain",
        ):
            if field in expected and field in fields:
                if normalize_observation_value(field, fields[field]) == normalize_observation_value(
                    field, expected[field]
                ):
                    score += 4
                else:
                    score -= 3
        candidates.append((score, fields))

    observations: dict[str, dict[str, object]] = {}
    if candidates:
        best_score = max(score for score, _ in candidates)
        best = [fields for score, fields in candidates if score == best_score]
        common = set(best[0])
        for fields in best[1:]:
            common.intersection_update(fields)
        for field in common:
            values = [normalize_observation_value(field, fields[field]) for fields in best]
            if any(value != values[0] for value in values[1:]):
                continue
            value: object = values[0]
            if field == "identity.year":
                value = configuration.year
            elif field == "identity.make":
                value = configuration.make
            elif field == "identity.model":
                value = configuration.model
            scope = (
                "model_year"
                if field.startswith("identity.") and field != "identity.drivetrain"
                else "powertrain_configuration"
            )
            observations[field] = _observation(value, scope=scope)

    return SourceExtraction(
        matched_fields={
            "year": "identity.year" in observations,
            "make": "identity.make" in observations,
            "model": "identity.model" in observations,
            "trim": None,
            "engine": None,
            "transmission": None,
            "configuration_match": False,
            "exact_configuration_scope": False,
            "reference_model": reference_model,
            "candidate_record_count": len(candidates),
            "observed_fields": sorted(observations),
            "field_observations": observations,
        },
        field_observations=observations,
    )


def extract_source(
    provider: str,
    raw: bytes,
    content_type: str,
    configuration: VehicleConfiguration,
) -> SourceExtraction:
    if provider == "nhtsa_vpic":
        return _extract_nhtsa(raw, configuration)
    if provider == "fueleconomy_gov":
        return _extract_fueleconomy(raw, configuration)
    return _extract_html(raw, content_type, configuration)


def match_source(
    provider: str,
    raw: bytes,
    content_type: str,
    configuration: VehicleConfiguration,
) -> dict[str, object]:
    return extract_source(provider, raw, content_type, configuration).matched_fields


def _cache(
    request: SourceRequest,
    raw: bytes,
    content_type: str,
    status: int,
    configuration: VehicleConfiguration,
    *,
    metadata: dict[str, object] | None = None,
) -> SourceFetchResult:
    digest = sha256(raw).hexdigest()
    suffix = ".json" if "json" in content_type.casefold() else ".html"
    relative = (
        Path(configuration.make)
        / str(configuration.year)
        / request.source_key
        / f"{digest}{suffix}"
    )
    destination = Path(settings.workbench_cache_root) / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(raw)
    extraction = extract_source(request.source_key, raw, content_type, configuration)
    raw_metadata: dict[str, object] = {
        "content_type": content_type,
        "bytes": len(raw),
        "extraction_method": EXTRACTION_METHOD,
    }
    if metadata:
        raw_metadata.update(metadata)
    return SourceFetchResult(
        provider=request.source_key,
        source_class=request.source_class,
        source_url=request.source_url,
        fetch_status="success",
        http_status=status,
        matched_fields=extraction.matched_fields,
        field_observations=extraction.field_observations,
        raw_sha256=digest,
        cache_path=str(relative),
        error=None,
        raw_metadata=raw_metadata,
    )


def fetch_source(request: SourceRequest, configuration: VehicleConfiguration) -> SourceFetchResult:
    try:
        if request.source_key == "fueleconomy_gov":
            raw, content_type, status = _fueleconomy_bundle(request.source_url)
        else:
            raw, content_type, status = _http(
                request.source_url,
                "text/html,application/json;q=0.9,application/xml;q=0.8,*/*;q=0.7",
            )
    except HTTPError as exc:
        status = int(exc.code)
        fetch_status = "not_found" if status == 404 else (
            "blocked" if status in {401, 403, 429} else "failed"
        )
        return SourceFetchResult(
            request.source_key,
            request.source_class,
            request.source_url,
            fetch_status,
            status,
            {},
            {},
            None,
            None,
            f"HTTP {status}",
            {},
        )
    except (URLError, TimeoutError, OSError, ValueError, ET.ParseError) as exc:
        return SourceFetchResult(
            request.source_key,
            request.source_class,
            request.source_url,
            "failed",
            None,
            {},
            {},
            None,
            None,
            str(exc)[:500],
            {},
        )
    return _cache(request, raw, content_type, status, configuration)


def replay_cached_source(
    request: SourceRequest,
    cache_path: str,
    configuration: VehicleConfiguration,
) -> SourceFetchResult | None:
    path = Path(settings.workbench_cache_root) / cache_path
    if not path.is_file():
        return None
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    content_type = "application/json" if path.suffix.casefold() == ".json" else "text/html"
    return _cache(
        request,
        raw,
        content_type,
        200,
        configuration,
        metadata={"cache_reused": True, "original_cache_path": cache_path},
    )
