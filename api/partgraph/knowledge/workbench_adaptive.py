from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
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
    observation_comparison_key,
)
from .workbench_source_pipeline import (
    MAX_RESPONSE_BYTES,
    USER_AGENT,
    SourceFetchResult,
    SourceRequest,
    extract_source,
    fetch_source,
    source_requests,
)


@dataclass(frozen=True, slots=True)
class SourceCapability:
    source_key: str
    phase: str
    priority: int
    field_prefixes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GapAnalysis:
    core_fields: tuple[str, ...]
    enrichment_fields: tuple[str, ...]

    @property
    def active_fields(self) -> tuple[str, ...]:
        # Finish exact seed applicability first. Once core identity/powertrain is
        # corroborated, use the same machinery to enrich unresolved technical
        # facts already discovered by broad extraction.
        return self.core_fields or self.enrichment_fields


@dataclass(frozen=True, slots=True)
class PlannedSourceRequest:
    request: SourceRequest
    phase: str
    requested_fields: tuple[str, ...]
    capability_groups: tuple[str, ...]


_REFERENCE_PREFIXES = (
    "identity.",
    "classification.",
    "powertrain.",
    "transmission.",
    "performance.",
    "efficiency.",
    "emissions.",
    "dimensions_weight.",
    "capacity.",
    "chassis.",
    "steering.",
    "suspension.",
    "brakes.",
    "wheels_tires.",
    "electrical.",
    "charging.",
    "safety.",
)

# The registry describes what a source is useful for and when to try it. It is
# not an allow-list and not an evidence ceiling. New reviewed adapters can be
# added without changing the scheduler or the three-independent-source rule.
_SOURCE_CAPABILITIES: dict[str, SourceCapability] = {
    "nhtsa_vpic": SourceCapability(
        "nhtsa_vpic",
        "broad",
        10,
        ("identity.year", "identity.make", "identity.model"),
    ),
    "fueleconomy_gov": SourceCapability(
        "fueleconomy_gov",
        "broad",
        20,
        (
            "identity.year",
            "identity.make",
            "identity.model",
            "identity.drivetrain",
            "classification.",
            "powertrain.engine.displacement_l",
            "powertrain.engine.cylinders",
            "powertrain.fuel_type",
            "transmission.family",
            "transmission.speeds",
            "efficiency.",
        ),
    ),
    "kbb": SourceCapability("kbb", "broad", 30, _REFERENCE_PREFIXES),
    "motortrend": SourceCapability("motortrend", "broad", 40, _REFERENCE_PREFIXES),
    # These are currently gap-fill adapters because they have historically
    # returned access-control responses in the local environment. The circuit
    # breaker still prevents repeated hammering if they remain unavailable.
    "cars_com": SourceCapability("cars_com", "gap", 100, _REFERENCE_PREFIXES),
    "edmunds": SourceCapability("edmunds", "gap", 110, _REFERENCE_PREFIXES),
}


def field_group(field: str) -> str:
    if field.startswith("identity.") or field.startswith("classification."):
        return "identity"
    if field.startswith("powertrain.engine.") or field.startswith("powertrain.electrification"):
        return "engine_powertrain"
    if field.startswith("performance."):
        return "performance"
    if field.startswith("transmission.") or field == "identity.drivetrain":
        return "transmission_drivetrain"
    if field.startswith("efficiency.") or field.startswith("emissions."):
        return "efficiency_emissions"
    if field.startswith("dimensions_weight.") or field.startswith("capacity."):
        return "dimensions_capacity"
    if (
        field.startswith("chassis.")
        or field.startswith("steering.")
        or field.startswith("suspension.")
        or field.startswith("brakes.")
        or field.startswith("wheels_tires.")
    ):
        return "chassis_running_gear"
    if field.startswith("electrical.") or field.startswith("charging."):
        return "electrical_charging"
    if field.startswith("safety."):
        return "safety"
    if field.startswith("service.") or field.startswith("fluids."):
        return "service_fluids"
    if field.startswith("parts.") or field.startswith("fitment."):
        return "parts_fitment"
    return "other_technical"


def _supports_field(capability: SourceCapability, field: str) -> bool:
    return any(field == prefix or field.startswith(prefix) for prefix in capability.field_prefixes)


def analyze_gaps(
    configuration: VehicleConfiguration,
    field_results: list[dict[str, object]],
) -> GapAnalysis:
    expected = core_configuration_fields(configuration)
    by_field = {
        item.get("field"): item
        for item in field_results
        if isinstance(item, dict) and isinstance(item.get("field"), str)
    }

    core: list[str] = []
    for field, expected_value in expected.items():
        result = by_field.get(field)
        status = result.get("status") if isinstance(result, dict) else None
        selected = result.get("selected_value") if isinstance(result, dict) else None
        matches = (
            status == "verified"
            and observation_comparison_key(field, selected)
            == observation_comparison_key(field, expected_value)
        )
        if not matches:
            core.append(field)

    enrichment: list[str] = []
    core_set = set(core)
    for item in field_results:
        field = item.get("field")
        status = item.get("status")
        if (
            isinstance(field, str)
            and field not in core_set
            and status in {"candidate", "conflict"}
            and not field.startswith(("service.", "fluids."))
        ):
            enrichment.append(field)

    return GapAnalysis(tuple(sorted(set(core))), tuple(sorted(set(enrichment))))


def plan_source_requests(
    configuration: VehicleConfiguration,
    gaps: GapAnalysis,
    observed_by_provider: dict[str, set[str]],
    attempted_providers: set[str],
    *,
    phase: str,
) -> tuple[PlannedSourceRequest, ...]:
    active = gaps.active_fields
    if not active:
        return ()

    plans: list[PlannedSourceRequest] = []
    for request in source_requests(configuration):
        capability = _SOURCE_CAPABILITIES.get(request.source_key)
        if capability is None or capability.phase != phase:
            continue
        if request.source_key in attempted_providers:
            continue
        relevant = tuple(sorted(field for field in active if _supports_field(capability, field)))
        if not relevant:
            continue
        already_observed = observed_by_provider.get(request.source_key, set())
        missing_from_provider = tuple(field for field in relevant if field not in already_observed)
        if not missing_from_provider:
            continue
        plans.append(
            PlannedSourceRequest(
                request=request,
                phase=phase,
                requested_fields=missing_from_provider,
                capability_groups=tuple(sorted({field_group(field) for field in missing_from_provider})),
            )
        )

    plans.sort(
        key=lambda item: (
            _SOURCE_CAPABILITIES[item.request.source_key].priority,
            item.request.source_key,
        )
    )
    return tuple(plans)


def source_capability_snapshot() -> dict[str, dict[str, object]]:
    return {
        key: {
            "phase": capability.phase,
            "priority": capability.priority,
            "field_prefixes": list(capability.field_prefixes),
        }
        for key, capability in sorted(_SOURCE_CAPABILITIES.items())
    }


def _tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def matching_fueleconomy_models(
    configuration: VehicleConfiguration,
    model_names: list[str],
) -> list[str]:
    """Resolve FuelEconomy model-menu names without hard-coding one model.

    FuelEconomy sometimes expands a base model into variants such as
    "CR-V 2WD" and "CR-V 4WD". The direct options endpoint can therefore
    return no rows for a valid PartGraph model. This resolver accepts only
    menu names whose normalized token string begins with the PartGraph model
    token string; downstream option-record scoring still resolves engine,
    transmission, and drivetrain variants.
    """
    base = "".join(_tokens(configuration.model))
    if not base:
        return []
    matches: list[str] = []
    for name in model_names:
        compact = "".join(_tokens(name))
        if compact == base or compact.startswith(base):
            matches.append(name)
    # Refuse an unexpectedly broad model match rather than turning a menu
    # naming ambiguity into fabricated applicability.
    return sorted(dict.fromkeys(matches))[:12]


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


def _menu_values(raw: bytes) -> list[str]:
    root = ET.fromstring(raw)
    values: list[str] = []
    for node in root.findall(".//menuItem/value"):
        if node.text and node.text.strip():
            values.append(node.text.strip())
    return values


def _xml_leaf_map(raw: bytes) -> dict[str, str]:
    root = ET.fromstring(raw)
    result: dict[str, str] = {}
    for node in root.iter():
        if len(node) == 0 and node.text and node.text.strip():
            result[node.tag.rsplit("}", 1)[-1]] = node.text.strip()
    return result


def _cache_adaptive_fueleconomy(
    request: SourceRequest,
    configuration: VehicleConfiguration,
    payload: dict[str, object],
    *,
    status: int,
) -> SourceFetchResult:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    digest = sha256(raw).hexdigest()
    relative = Path(configuration.make) / str(configuration.year) / request.source_key / f"{digest}.json"
    destination = Path(settings.workbench_cache_root) / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(raw)

    extraction = extract_source(request.source_key, raw, "application/json", configuration)
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
        raw_metadata={
            "content_type": "application/json",
            "bytes": len(raw),
            "adaptive_model_discovery": True,
            "resolved_models": payload.get("resolved_models", []),
            "detail_errors": payload.get("detail_errors", []),
        },
    )


def _fueleconomy_model_discovery(
    request: SourceRequest,
    configuration: VehicleConfiguration,
) -> SourceFetchResult | None:
    model_query = urlencode({"year": configuration.year, "make": configuration.make})
    model_url = f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/model?{model_query}"
    try:
        raw_models, _content_type, status = _http(model_url, "application/xml,text/xml;q=0.9")
        resolved_models = matching_fueleconomy_models(configuration, _menu_values(raw_models))
        if not resolved_models:
            return None

        vehicle_ids: list[str] = []
        option_errors: list[dict[str, str]] = []
        for model in resolved_models:
            options_query = urlencode(
                {"year": configuration.year, "make": configuration.make, "model": model}
            )
            options_url = f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/options?{options_query}"
            try:
                raw_options, _option_type, _option_status = _http(
                    options_url, "application/xml,text/xml;q=0.9"
                )
                vehicle_ids.extend(_menu_values(raw_options))
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, ET.ParseError) as exc:
                option_errors.append({"model": model, "error": str(exc)[:300]})

        records: list[dict[str, str]] = []
        detail_errors: list[dict[str, str]] = []
        for vehicle_id in list(dict.fromkeys(vehicle_ids)):
            try:
                raw_detail, _detail_type, _detail_status = _http(
                    f"https://www.fueleconomy.gov/ws/rest/vehicle/{quote(vehicle_id)}",
                    "application/xml,text/xml;q=0.9",
                )
                record = _xml_leaf_map(raw_detail)
                record["_vehicle_id"] = vehicle_id
                records.append(record)
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, ET.ParseError) as exc:
                detail_errors.append({"vehicle_id": vehicle_id, "error": str(exc)[:300]})

        return _cache_adaptive_fueleconomy(
            request,
            configuration,
            {
                "records": records,
                "resolved_models": resolved_models,
                "option_errors": option_errors,
                "detail_errors": detail_errors,
                "model_menu_url": model_url,
            },
            status=status,
        )
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, ET.ParseError):
        return None


def fetch_source_adaptive(
    request: SourceRequest,
    configuration: VehicleConfiguration,
    *,
    primary_result: SourceFetchResult | None = None,
) -> SourceFetchResult:
    """Fetch broadly first, with a narrow deterministic fallback where proven needed."""
    result = primary_result or fetch_source(request, configuration)
    if request.source_key != "fueleconomy_gov":
        return result
    if result.fetch_status != "success" or result.field_observations:
        return result

    discovered = _fueleconomy_model_discovery(request, configuration)
    if discovered is not None:
        return discovered
    return result
