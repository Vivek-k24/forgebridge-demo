import json

from partgraph.collectors.ebay import EbayCatalogClient, VehicleApplication
from partgraph.collectors.staging import (
    CandidateType,
    observation_dedupe_key,
    raw_payload_sha256,
)


def test_raw_hash_and_dedupe_are_deterministic():
    first = {"b": 2, "a": 1}
    second = {"a": 1, "b": 2}
    first_hash = raw_payload_sha256(first)
    assert first_hash == raw_payload_sha256(second)
    assert observation_dedupe_key(
        source_name="source",
        source_record_id="record-1",
        raw_sha256=first_hash,
    ) == observation_dedupe_key(
        source_name="source",
        source_record_id="record-1",
        raw_sha256=first_hash,
    )


def test_trim_observations_expand_trim_and_engine_taxonomy():
    def transport(method, url, headers, body):
        assert headers["Authorization"] == "Bearer test-token"
        payload = json.loads(body.decode("utf-8"))
        if payload["propertyName"] == "Trim":
            return {"metadataVersion": "1", "propertyValues": ["EX", "LX"]}
        trim = next(
            value["propertyValue"]
            for value in payload["propertyFilters"]
            if value["propertyName"] == "Trim"
        )
        return {
            "metadataVersion": "1",
            "propertyValues": ["1.8L I4"] if trim == "EX" else ["2.0L I4"],
        }

    client = EbayCatalogClient(access_token="test-token", transport=transport)
    observations = client.trim_observations(
        category_id="33707", year=2012, make="Honda", model="Civic"
    )

    assert [record.candidate_type for record in observations] == [
        CandidateType.VEHICLE_TRIM,
        CandidateType.VEHICLE_TRIM,
    ]
    assert {record.candidate_payload["trim"] for record in observations} == {"EX", "LX"}
    assert {record.candidate_payload["engine"] for record in observations} == {
        "1.8L I4",
        "2.0L I4",
    }


def test_inventory_observations_keep_raw_offer_part_and_fitment_candidates():
    def transport(method, url, headers, body):
        assert method == "GET"
        assert "compatibility_filter=" in url
        return {
            "itemSummaries": [
                {
                    "itemId": "v1|123|0",
                    "title": "Example Brake Pad Set",
                    "condition": "New",
                    "itemWebUrl": "https://example.test/item/123",
                    "price": {"value": "29.99", "currency": "USD"},
                    "localizedAspects": [
                        {"name": "Brand", "value": "ExampleBrand"},
                        {"name": "Manufacturer Part Number", "value": "BP-123"},
                    ],
                    "compatibilityMatch": "EXACT",
                    "compatibilityProperties": [
                        {"name": "Year", "value": "2012"},
                        {"name": "Make", "value": "Honda"},
                        {"name": "Model", "value": "Civic"},
                    ],
                }
            ]
        }

    client = EbayCatalogClient(access_token="test-token", transport=transport)
    vehicle = VehicleApplication(2012, "Honda", "Civic", "EX", "1.8L I4")
    observations = client.inventory_observations(
        query="brake pads", category_id="33559", vehicle=vehicle
    )

    assert [record.candidate_type for record in observations] == [
        CandidateType.INVENTORY_OFFER,
        CandidateType.PART,
        CandidateType.PART_FITMENT,
    ]
    assert observations[0].candidate_payload["price"] == "29.99"
    assert observations[1].candidate_payload["manufacturer_part_number"] == "BP-123"
    assert observations[2].candidate_payload["submitted_vehicle"]["trim"] == "EX"
    assert observations[2].candidate_payload["compatibility_match"] == "EXACT"
