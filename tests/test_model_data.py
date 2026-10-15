import pytest

from edflow.model_data import (
    FEATURE_COLUMNS,
    TARGET_COLUMNS,
    build_arrival_training_rows,
)


def sample_records():
    encounter = {
        "encounter_id": "EN1",
        "patient_id": "P1",
        "hospital_id": "H1",
        "arrival_at": "2025-01-01T01:00:00+00:00",
        "arrival_mode": "walk_in",
        "triage_category": 3,
        "departure_status": "admitted",
        "waiting_time_minutes": 35.0,
        "admitted_flag": 1,
        "four_hour_breach": 0,
    }
    snapshot = {
        "encounter_id": "EN1",
        "patient_id": "P1",
        "hospital_id": "H1",
        "arrival_at": "2025-01-01T01:00:00+00:00",
        "untriaged_patients": 2,
        "waiting_for_treatment": 4,
        "in_treatment": 3,
        "arrivals_last_60m": 8,
        "departures_last_60m": 5,
    }
    patient = {
        "patient_id": "P1",
        "birth_date": "1980-01-02",
        "chronic_condition_count": 2,
        "sex": "female",
    }
    return encounter, snapshot, patient


def test_training_features_are_available_at_arrival():
    encounter, snapshot, patient = sample_records()
    rows = build_arrival_training_rows(
        [encounter], [snapshot], [patient]
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["age_years"] == 44
    assert row["waiting_for_treatment"] == 4
    assert row["waiting_time_minutes"] == 35.0
    assert row["admitted_flag"] == 1
    assert set(FEATURE_COLUMNS).isdisjoint(TARGET_COLUMNS)
    assert "triage_category" not in row
    assert "departure_status" not in row


def test_rejects_mismatched_snapshot():
    encounter, snapshot, patient = sample_records()
    snapshot["hospital_id"] = "H2"

    with pytest.raises(ValueError, match="snapshot does not match"):
        build_arrival_training_rows(
            [encounter], [snapshot], [patient]
        )


def test_rejects_duplicate_snapshots():
    encounter, snapshot, patient = sample_records()

    with pytest.raises(ValueError, match="duplicate encounter_id"):
        build_arrival_training_rows(
            [encounter], [snapshot, snapshot], [patient]
        )