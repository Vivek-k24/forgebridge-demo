from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from .extraction import (
    MECHANICAL_CLAIM_CAPABILITY,
    ExtractedCandidate,
    ExtractionError,
    ProviderMetadata,
    RawProviderRecord,
    SourceMetadata,
    StagedExtractionResult,
    extract_and_stage_provider_record,
)

NHTSA_RECALLS_ENDPOINT = "https://api.nhtsa.gov/recalls/recallsByVehicle"
NHTSA_COLLECTOR_KEY = "nhtsa_vehicle_recalls"
NHTSA_COLLECTOR_VERSION = "v1"
MAX_RESPONSE_BYTES = 2_000_000
MAX_RECALLS_PER_QUERY = 1000


@dataclass(frozen=True, slots=True)
class NhtsaVehicleQuery:
    year: int
    make: str
    model: str

    def __post_init__(self) -> None:
        if not 1996 <= self.year <= 2100:
            raise ExtractionError("NHTSA vehicle query year must be between 1996 and 2100")
        if not " ".join(self.make.split()):
            raise ExtractionError("NHTSA vehicle query make is required")
        if not " ".join(self.model.split()):
            raise ExtractionError("NHTSA vehicle query model is required")

    @property
    def normalized_make(self) -> str:
        return " ".join(self.make.split())

    @property
    def normalized_model(self) -> str:
        return " ".join(self.model.split())


class _NhtsaRecall(BaseModel):
    model_config = ConfigDict(extra="ignore")

    manufacturer: str = Field(alias="Manufacturer", min_length=1)
    campaign_number: str = Field(alias="NHTSACampaignNumber", min_length=1)
    park_it: bool = Field(default=False, alias="parkIt")
    park_outside: bool = Field(default=False, alias="parkOutSide")
    over_the_air_update: bool = Field(default=False, alias="overTheAirUpdate")
    nhtsa_action_number: str | None = Field(default=None, alias="NHTSAActionNumber")
    report_received_date: str = Field(alias="ReportReceivedDate", min_length=1)
    component: str = Field(alias="Component", min_length=1)
    summary: str = Field(alias="Summary", min_length=1)
    consequence: str = Field(alias="Consequence", min_length=1)
    remedy: str = Field(alias="Remedy", min_length=1)
    model_year: int = Field(alias="ModelYear", ge=1996, le=2100)
    make: str = Field(alias="Make", min_length=1)
    model: str = Field(alias="Model", min_length=1)


class _NhtsaRecallResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    count: int = Field(alias="Count", ge=0, le=MAX_RECALLS_PER_QUERY)
    message: str = Field(alias="Message")
    results: list[_NhtsaRecall] = Field(default_factory=list, max_length=MAX_RECALLS_PER_QUERY)

    @model_validator(mode="after")
    def validate_count(self) -> _NhtsaRecallResponse:
        if self.count != len(self.results):
            raise ValueError("NHTSA response count does not match result rows")
        return self


def _clean(value: str) -> str:
    return " ".join(value.split())


def build_nhtsa_recall_url(query: NhtsaVehicleQuery) -> str:
    params = urlencode(
        {
            "make": query.normalized_make,
            "model": query.normalized_model,
            "modelYear": query.year,
        }
    )
    return f"{NHTSA_RECALLS_ENDPOINT}?{params}"


def _fetch_json(url: str, *, timeout_seconds: float) -> dict[str, object]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "PartGraph-NHTSA-Collector/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - URL is fixed above
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except (TimeoutError, URLError, OSError) as exc:
        raise ExtractionError("NHTSA recall request failed") from exc

    if len(body) > MAX_RESPONSE_BYTES:
        raise ExtractionError("NHTSA recall response exceeded the collector size limit")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtractionError("NHTSA recall response was not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ExtractionError("NHTSA recall response must be a JSON object")
    return payload


class NhtsaRecallCollector:
    """Fetch one official NHTSA recall response for a broad vehicle identity."""

    def __init__(self, *, timeout_seconds: float = 10.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds

    async def fetch(self, query: NhtsaVehicleQuery) -> RawProviderRecord:
        url = build_nhtsa_recall_url(query)
        payload = await asyncio.to_thread(
            _fetch_json,
            url,
            timeout_seconds=self.timeout_seconds,
        )
        fetched_at = datetime.now(UTC)
        return RawProviderRecord(
            source_record_id=(
                f"recallsByVehicle:{query.year}:"
                f"{query.normalized_make}:{query.normalized_model}"
            ),
            source_url=url,
            fetched_at=fetched_at,
            raw_payload=payload,
            provenance={
                "collector_key": NHTSA_COLLECTOR_KEY,
                "collector_version": NHTSA_COLLECTOR_VERSION,
                "authority": "National Highway Traffic Safety Administration",
                "query_year": query.year,
                "query_make": query.normalized_make,
                "query_model": query.normalized_model,
            },
            observed_at=fetched_at,
        )


class NhtsaRecallAdapter:
    """Keep safety-recall facts and discard unrelated provider fields."""

    adapter_key = "nhtsa_recalls"
    adapter_version = "v1"
    required_capability = MECHANICAL_CLAIM_CAPABILITY
    supported_provider_kinds = frozenset({"vehicle_data"})

    def extract(self, record: RawProviderRecord) -> tuple[ExtractedCandidate, ...]:
        try:
            document = _NhtsaRecallResponse.model_validate(record.raw_payload)
        except ValidationError as exc:
            raise ExtractionError("NHTSA recall response did not match the expected contract") from exc

        candidates: list[ExtractedCandidate] = []
        for recall in document.results:
            campaign_number = _clean(recall.campaign_number).upper()
            applicability = {
                "market": "US",
                "year": recall.model_year,
                "make": _clean(recall.make),
                "model": _clean(recall.model),
                "scope": "year_make_model",
            }
            claim_payload: dict[str, object] = {
                "campaign_number": campaign_number,
                "manufacturer": _clean(recall.manufacturer),
                "component": _clean(recall.component),
                "issue": _clean(recall.summary),
                "consequence": _clean(recall.consequence),
                "remedy": _clean(recall.remedy),
                "report_received_date": _clean(recall.report_received_date),
                "park_it": recall.park_it,
                "park_outside": recall.park_outside,
                "over_the_air_update": recall.over_the_air_update,
                "applicability": applicability,
            }
            if recall.nhtsa_action_number and _clean(recall.nhtsa_action_number):
                claim_payload["nhtsa_action_number"] = _clean(recall.nhtsa_action_number)

            candidates.append(
                ExtractedCandidate(
                    candidate_type="mechanical_claim_candidate",
                    candidate_payload={
                        "mechanical_claim": {
                            "claim_domain": "safety_campaign",
                            "claim_risk": "safety_critical",
                            "normalized_key": f"nhtsa.recall.{campaign_number.casefold()}",
                            "claim_payload": claim_payload,
                            "explicit_claim": True,
                            "exact_applicability": False,
                            "vehicle_configuration_id": None,
                            "repair_key": None,
                        }
                    },
                )
            )
        return tuple(candidates)


async def collect_and_stage_nhtsa_recalls(
    session: AsyncSession,
    *,
    provider: ProviderMetadata,
    source: SourceMetadata,
    query: NhtsaVehicleQuery,
    collector: NhtsaRecallCollector | None = None,
) -> StagedExtractionResult:
    """Fetch NHTSA recalls and stage them as pending, non-exact candidate facts."""

    active_collector = collector or NhtsaRecallCollector()
    record = await active_collector.fetch(query)
    return await extract_and_stage_provider_record(
        session,
        provider=provider,
        source=source,
        adapter=NhtsaRecallAdapter(),
        record=record,
    )
