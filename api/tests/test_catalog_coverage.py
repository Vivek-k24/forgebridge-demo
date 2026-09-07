from fastapi.testclient import TestClient

from partgraph.main import app

BATCH_KEY = "selected-asian-1996-2000-v1"
EXPECTED_MAKES = {
    "Acura": 62,
    "Honda": 114,
    "Lexus": 18,
    "Subaru": 63,
    "Toyota": 106,
}


def test_workbook_batch_reports_seed_candidates_before_collection() -> None:
    with TestClient(app) as client:
        response = client.get(f"/api/v1/catalog-coverage/batches/{BATCH_KEY}")

    assert response.status_code == 200
    body = response.json()
    assert body["batch_key"] == BATCH_KEY
    assert body["target_rows"] == 363
    assert body["verification_rule"] == "three_independent_sources"
    assert body["candidates"] == 363
    assert body["collected"] == 0
    assert body["verified"] == 0
    assert body["conflict"] == 0
    assert body["collection_remaining"] == 363
    assert body["verification_remaining"] == 363
    assert body["collection_percent"] == 0.0
    assert body["verification_percent"] == 0.0
    assert body["scope"]["artifact"] == "Selected_Asian_Brands_1996_2000.xlsx"
    assert body["scope"]["repository_commit"] == (
        "ab954125d89f8ae4cfc42d35af177ec1fe3938a8"
    )
    assert {row["make"]: row["candidates"] for row in body["makes"]} == EXPECTED_MAKES
    assert all(row["collected"] == 0 for row in body["makes"])
    assert all(row["verified"] == 0 for row in body["makes"])
    assert all(row["collection_remaining"] == row["candidates"] for row in body["makes"])
    assert all(row["verification_remaining"] == row["candidates"] for row in body["makes"])


def test_catalog_coverage_batch_list_contains_workbook_batch() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/catalog-coverage/batches")

    assert response.status_code == 200
    batches = response.json()
    workbook = next(item for item in batches if item["batch_key"] == BATCH_KEY)
    assert workbook["candidates"] == 363
    assert workbook["collected"] == 0
    assert sum(row["candidates"] for row in workbook["makes"]) == 363


def test_unknown_catalog_coverage_batch_is_not_found() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/catalog-coverage/batches/not-a-real-batch")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == "catalog coverage batch not found"