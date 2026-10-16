from fastapi.testclient import TestClient

from edflow.__main__ import main as generate_run
from edflow.api import create_app


def test_api_serves_generated_run_and_return_audit(tmp_path):
    run = tmp_path / "run"
    generate_run([
        "--output", str(run),
        "--hours", "24",
        "--patients", "500",
        "--seed", "7",
        "--generator-version", "2",
    ])

    client = TestClient(create_app(run))

    assert client.get("/health").json() == {"status": "ok"}

    manifest = client.get("/api/manifest").json()
    assert manifest["encounter_count"] > 0

    hospitals = client.get("/api/hospitals").json()
    assert len(hospitals) == manifest["hospital_kpi_count"]

    hospital_id = hospitals[0]["hospital_id"]
    daily = client.get(
        "/api/daily",
        params={"hospital_id": hospital_id},
    ).json()
    assert all(row["hospital_id"] == hospital_id for row in daily)

    assert client.get(
        "/api/daily",
        params={"hospital_id": "unknown"},
    ).status_code == 400

    audit = client.get("/api/representation").json()
    assert audit["available"]
    assert audit["overlapping_arrivals"] == 0

    events = client.get("/api/events", params={"limit": 5}).json()
    assert len(events) == 5
    assert all("event_id" in event for event in events)
    assert client.get("/api/events?limit=0").status_code == 422