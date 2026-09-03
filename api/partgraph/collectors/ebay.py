"""eBay Motors adapters for trim taxonomy and live parts observations.

The eBay data produced here is discovery/procurement evidence only. Every
observation is intended for ``catalog_staging`` and must pass PartGraph's
source-governance and verification boundary before canonical promotion.
"""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .staging import CandidateType

JsonDict = dict[str, Any]
Transport = Callable[[str, str, dict[str, str], bytes | None], JsonDict]


class EbayCatalogError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class VehicleApplication:
    year: int
    make: str
    model: str
    trim: str | None = None
    engine: str | None = None

    def as_dict(self) -> JsonDict:
        payload: JsonDict = {
            "year": self.year,
            "make": self.make,
            "model": self.model,
        }
        if self.trim:
            payload["trim"] = self.trim
        if self.engine:
            payload["engine"] = self.engine
        return payload

    def compatibility_filter(self) -> str:
        values = [("Year", str(self.year)), ("Make", self.make), ("Model", self.model)]
        if self.trim:
            values.append(("Trim", self.trim))
        if self.engine:
            values.append(("Engine", self.engine))
        return ";".join(f"{name}:{value}" for name, value in values)


@dataclass(frozen=True, slots=True)
class CollectedObservation:
    source_record_id: str
    source_url: str
    candidate_type: CandidateType
    raw_payload: JsonDict
    candidate_payload: JsonDict
    vehicle_identity: JsonDict | None
    provenance: JsonDict
    extraction_method: str


def _default_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    body: bytes | None,
) -> JsonDict:
    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, timeout=45) as response:  # noqa: S310 - fixed trusted API hosts
        return json.loads(response.read().decode("utf-8"))


def _property_values(payload: JsonDict) -> list[str]:
    values: list[str] = []
    for value in payload.get("propertyValues", []):
        if isinstance(value, str):
            values.append(value)
            continue
        if isinstance(value, dict):
            candidate = value.get("value") or value.get("propertyValue")
            if isinstance(candidate, str) and candidate:
                values.append(candidate)
    return sorted(set(values))


def _localized_aspects(item: JsonDict) -> dict[str, str]:
    aspects: dict[str, str] = {}
    for aspect in item.get("localizedAspects", []):
        if not isinstance(aspect, dict):
            continue
        name = aspect.get("name")
        value = aspect.get("value")
        if isinstance(name, str) and isinstance(value, str):
            aspects[name.casefold()] = value
    return aspects


class EbayCatalogClient:
    TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
    METADATA_VALUES_URL = (
        "https://api.ebay.com/sell/metadata/v1/compatibilities/"
        "get_compatibility_property_values"
    )
    BROWSE_SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"

    def __init__(
        self,
        *,
        access_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        metadata_marketplace: str = "EBAY_MOTORS_US",
        browse_marketplace: str = "EBAY_US",
        transport: Transport | None = None,
    ) -> None:
        self.access_token = access_token or os.getenv("EBAY_ACCESS_TOKEN")
        self.client_id = client_id or os.getenv("EBAY_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("EBAY_CLIENT_SECRET")
        self.metadata_marketplace = metadata_marketplace
        self.browse_marketplace = browse_marketplace
        self.transport = transport or _default_transport

    def _token(self) -> str:
        if self.access_token:
            return self.access_token
        if not self.client_id or not self.client_secret:
            raise EbayCatalogError(
                "configure EBAY_ACCESS_TOKEN or EBAY_CLIENT_ID + EBAY_CLIENT_SECRET"
            )
        basic = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode("ascii")
        body = urlencode(
            {
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            }
        ).encode("ascii")
        response = self.transport(
            "POST",
            self.TOKEN_URL,
            {
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
            body,
        )
        token = response.get("access_token")
        if not isinstance(token, str) or not token:
            raise EbayCatalogError("eBay OAuth response did not contain an access token")
        self.access_token = token
        return token

    def _headers(self, *, marketplace: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": marketplace,
        }

    def compatibility_property_values(
        self,
        *,
        category_id: str,
        property_name: str,
        filters: Iterable[tuple[str, str]] = (),
    ) -> JsonDict:
        payload = {
            "categoryId": category_id,
            "propertyName": property_name,
            "propertyFilters": [
                {"propertyName": name, "propertyValue": value} for name, value in filters
            ],
        }
        return self.transport(
            "POST",
            self.METADATA_VALUES_URL,
            self._headers(marketplace=self.metadata_marketplace),
            json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        )

    def trim_observations(
        self,
        *,
        category_id: str,
        year: int,
        make: str,
        model: str,
    ) -> list[CollectedObservation]:
        base_filters = (("Year", str(year)), ("Make", make), ("Model", model))
        trim_response = self.compatibility_property_values(
            category_id=category_id,
            property_name="Trim",
            filters=base_filters,
        )
        observations: list[CollectedObservation] = []
        for trim in _property_values(trim_response):
            engine_response = self.compatibility_property_values(
                category_id=category_id,
                property_name="Engine",
                filters=(*base_filters, ("Trim", trim)),
            )
            engines: list[str | None] = _property_values(engine_response) or [None]
            for engine in engines:
                application = VehicleApplication(year, make, model, trim, engine)
                identity = application.as_dict()
                suffix = engine or "unknown-engine"
                observations.append(
                    CollectedObservation(
                        source_record_id=(
                            f"compat:{category_id}:{year}:{make}:{model}:{trim}:{suffix}"
                        ),
                        source_url=self.METADATA_VALUES_URL,
                        candidate_type=CandidateType.VEHICLE_TRIM,
                        raw_payload={
                            "query": {
                                "category_id": category_id,
                                "filters": list(base_filters),
                            },
                            "trim_response": trim_response,
                            "engine_response": engine_response,
                        },
                        candidate_payload=identity,
                        vehicle_identity=identity,
                        provenance={
                            "provider": "ebay",
                            "dataset": "motors_compatibility_metadata",
                            "marketplace": self.metadata_marketplace,
                            "category_id": category_id,
                        },
                        extraction_method="ebay_metadata_api",
                    )
                )
        return observations

    def search_parts(
        self,
        *,
        query: str,
        category_id: str,
        vehicle: VehicleApplication,
        limit: int = 50,
    ) -> JsonDict:
        if limit < 1 or limit > 200:
            raise ValueError("eBay Browse limit must be between 1 and 200")
        params = urlencode(
            {
                "q": query,
                "category_ids": category_id,
                "compatibility_filter": vehicle.compatibility_filter(),
                "limit": str(limit),
            }
        )
        return self.transport(
            "GET",
            f"{self.BROWSE_SEARCH_URL}?{params}",
            self._headers(marketplace=self.browse_marketplace),
            None,
        )

    def inventory_observations(
        self,
        *,
        query: str,
        category_id: str,
        vehicle: VehicleApplication,
        limit: int = 50,
    ) -> list[CollectedObservation]:
        response = self.search_parts(
            query=query,
            category_id=category_id,
            vehicle=vehicle,
            limit=limit,
        )
        observations: list[CollectedObservation] = []
        identity = vehicle.as_dict()
        for item in response.get("itemSummaries", []):
            if not isinstance(item, dict):
                continue
            item_id = item.get("itemId")
            if not isinstance(item_id, str) or not item_id:
                continue
            item_url = item.get("itemWebUrl")
            source_url = (
                item_url
                if isinstance(item_url, str) and item_url
                else self.BROWSE_SEARCH_URL
            )
            common_raw = {
                "search": {
                    "query": query,
                    "category_id": category_id,
                    "vehicle": identity,
                },
                "item": item,
            }
            price = item.get("price") if isinstance(item.get("price"), dict) else {}
            inventory_candidate: JsonDict = {
                "provider": "ebay",
                "provider_item_id": item_id,
                "title": item.get("title"),
                "condition": item.get("condition"),
                "price": price.get("value"),
                "currency": price.get("currency"),
                "item_url": source_url,
            }
            observations.append(
                CollectedObservation(
                    source_record_id=f"item:{item_id}:inventory",
                    source_url=source_url,
                    candidate_type=CandidateType.INVENTORY_OFFER,
                    raw_payload=common_raw,
                    candidate_payload=inventory_candidate,
                    vehicle_identity=identity,
                    provenance={
                        "provider": "ebay",
                        "dataset": "browse_live_listing",
                        "marketplace": self.browse_marketplace,
                        "category_id": category_id,
                    },
                    extraction_method="ebay_browse_api",
                )
            )

            aspects = _localized_aspects(item)
            part_candidate: JsonDict = {
                "provider_item_id": item_id,
                "title": item.get("title"),
                "brand": aspects.get("brand"),
                "manufacturer_part_number": (
                    aspects.get("manufacturer part number") or aspects.get("mpn")
                ),
            }
            observations.append(
                CollectedObservation(
                    source_record_id=f"item:{item_id}:part",
                    source_url=source_url,
                    candidate_type=CandidateType.PART,
                    raw_payload=common_raw,
                    candidate_payload=part_candidate,
                    vehicle_identity=identity,
                    provenance={
                        "provider": "ebay",
                        "dataset": "browse_live_listing",
                        "marketplace": self.browse_marketplace,
                        "category_id": category_id,
                    },
                    extraction_method="ebay_browse_api",
                )
            )

            compatibility = item.get("compatibilityProperties")
            if isinstance(compatibility, list) and compatibility:
                returned = {
                    str(prop.get("name")): prop.get("value")
                    for prop in compatibility
                    if isinstance(prop, dict) and prop.get("name")
                }
                observations.append(
                    CollectedObservation(
                        source_record_id=f"item:{item_id}:fitment",
                        source_url=source_url,
                        candidate_type=CandidateType.PART_FITMENT,
                        raw_payload=common_raw,
                        candidate_payload={
                            "provider_item_id": item_id,
                            "submitted_vehicle": identity,
                            "returned_compatibility": returned,
                            "compatibility_match": item.get("compatibilityMatch"),
                        },
                        vehicle_identity=identity,
                        provenance={
                            "provider": "ebay",
                            "dataset": "browse_parts_compatibility",
                            "marketplace": self.browse_marketplace,
                            "category_id": category_id,
                        },
                        extraction_method="ebay_browse_api",
                    )
                )
        return observations
