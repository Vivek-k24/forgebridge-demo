from fastapi.testclient import TestClient

from partgraph.main import app
from partgraph.vehicle.policy import MIN_SUPPORTED_YEAR, max_supported_year


def _params(year: int) -> dict[str, object]:
    return {
        "year": year,
        "market": "US",
        "make": "Honda",
    }


def test_year_policy_is_1996_through_current_calendar_year() -> None:
    assert MIN_SUPPORTED_YEAR == 1996
    assert max_supported_year() >= MIN_SUPPORTED_YEAR

    with TestClient(app) as client:
        oldest = client.get("/api/v1/vehicle-options/models", params=_params(1996))
        newest = client.get(
            "/api/v1/vehicle-options/models",
            params=_params(max_supported_year()),
        )
        too_old = client.get("/api/v1/vehicle-options/models", params=_params(1995))
        future = client.get(
            "/api/v1/vehicle-options/models",
            params=_params(max_supported_year() + 1),
        )

    assert oldest.status_code == 200
    assert newest.status_code == 200
    assert too_old.status_code == 422
    assert future.status_code == 422
    assert "1996" in str(too_old.json())
    assert str(max_supported_year()) in str(future.json())


def test_brand_scope_keeps_volvo_volkswagen_and_isuzu_but_excludes_modern_ev_brands() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/vehicle-brands")

    assert response.status_code == 200
    brands = {item["name"]: item["status"] for item in response.json()}
    assert brands["Volvo"] == "active"
    assert brands["Volkswagen"] == "active"
    assert brands["Isuzu"] == "legacy"
    assert "Tesla" not in brands
    assert "Rivian" not in brands
    assert "Lucid" not in brands
