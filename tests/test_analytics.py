from datetime import datetime, timedelta, timezone

import pytest

from edflow.analytics import build_hospital_kpis


BASE = datetime(2025, 1, 1, tzinfo=timezone.utc)


def encounter(
    encounter_id, hospital_id, arrival_hour, wait, stay, admitted
):
    arrival = BASE + timedelta(hours=arrival_hour)
    return {
        "encounter_id": encounter_id,
        "patient_id": f"P-{encounter_id}",
        "hospital_id": hospital_id,
        "arrival_at": arrival.isoformat(),
        "arrival_mode": "walk_in",
        "triage_at": (arrival + timedelta(minutes=5)).isoformat(),
        "triage_category": 3,
        "presentation_group": "injury",
        "treatment_start_at": (
            arrival + timedelta(minutes=wait)
        ).isoformat(),
        "departure_at": (
            arrival + timedelta(minutes=stay)
        ).isoformat(),
        "departure_status": "admitted" if admitted else "discharged",
        "admitted_flag": int(admitted),
        "waiting_time_minutes": wait,
        "ed_length_of_stay_minutes": stay,
        "four_hour_breach": int(stay > 240),
    }


def test_hospital_and_daily_kpis():
    rows = [
        encounter("A", "H1", 1, 10, 100, False),
        encounter("B", "H1", 25, 30, 300, True),
        encounter("C", "H2", 2, 20, 200, False),
    ]

    hospitals, daily = build_hospital_kpis(rows)

    assert hospitals[0] == {
        "hospital_id": "H1",
        "presentation_count": 2,
        "median_waiting_time_minutes": 20,
        "median_ed_length_of_stay_minutes": 200,
        "four_hour_completion_rate": 0.5,
        "admission_rate": 0.5,
    }
    assert hospitals[1]["presentation_count"] == 1
    assert hospitals[1]["four_hour_completion_rate"] == 1
    assert [
        (row["hospital_id"], row["arrival_date_utc"])
        for row in daily
    ] == [
        ("H1", "2025-01-01"),
        ("H1", "2025-01-02"),
        ("H2", "2025-01-01"),
    ]


def test_rejects_incorrect_outcome_label():
    row = encounter("A", "H1", 1, 10, 100, False)
    row["four_hour_breach"] = 1

    with pytest.raises(ValueError, match="four_hour_breach"):
        build_hospital_kpis([row])


def test_rejects_duplicate_encounter():
    row = encounter("A", "H1", 1, 10, 100, False)

    with pytest.raises(ValueError, match="duplicate encounter"):
        build_hospital_kpis([row, row])