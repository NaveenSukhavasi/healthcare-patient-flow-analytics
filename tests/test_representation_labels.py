from datetime import datetime, timedelta, timezone

import pytest

from edflow.representation_audit import audit_representation
from edflow.representation_labels import build_representation_labels


START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def visit(encounter_id, patient_id, arrival, departure, status="discharged"):
    return {
        "encounter_id": encounter_id,
        "patient_id": patient_id,
        "arrival_at": arrival.isoformat(),
        "departure_at": departure.isoformat(),
        "departure_status": status,
    }


def test_labels_match_audit_counts_and_seven_day_boundary():
    first_departure = START + timedelta(hours=1)
    rows = [
        visit("EN1", "P1", START, first_departure),
        visit(
            "EN2", "P1",
            first_departure + timedelta(days=7),
            first_departure + timedelta(days=7, hours=1),
        ),
        visit(
            "EN3", "P2",
            START + timedelta(days=1),
            START + timedelta(days=1, hours=1),
            status="admitted",
        ),
        visit(
            "EN4", "P3",
            START + timedelta(days=12),
            START + timedelta(days=12, hours=1),
        ),
        visit(
            "EN5", "P4",
            START + timedelta(days=1),
            START + timedelta(days=1, hours=1),
        ),
    ]

    labels = build_representation_labels(rows, START.isoformat(), 336)
    by_id = {row["encounter_id"]: row for row in labels}
    audit = audit_representation(rows, START.isoformat(), 336)

    assert by_id["EN1"]["seven_day_return"] == 1
    assert by_id["EN1"]["label_available_at"] == (
        first_departure + timedelta(days=7)
    ).isoformat()
    assert by_id["EN2"]["followup_status"] == "censored"
    assert by_id["EN3"]["followup_status"] == "admitted"
    assert by_id["EN4"]["seven_day_return"] is None
    assert by_id["EN5"]["seven_day_return"] == 0

    assert sum(row["followup_status"] == "eligible" for row in labels) == (
        audit["eligible_seven_day_followups"]
    )
    assert sum(row["followup_status"] == "censored" for row in labels) == (
        audit["censored_followups"]
    )
    assert sum(row["followup_status"] == "admitted" for row in labels) == (
        audit["excluded_admitted_indices"]
    )
    assert sum(row["seven_day_return"] == 1 for row in labels) == (
        audit["apparent_seven_day_returns"]
    )


def test_rejects_overlapping_encounters():
    rows = [
        visit("EN1", "P1", START, START + timedelta(hours=2)),
        visit(
            "EN2", "P1",
            START + timedelta(hours=1),
            START + timedelta(hours=3),
        ),
    ]

    with pytest.raises(ValueError, match="overlapping"):
        build_representation_labels(rows, START.isoformat(), 336)


def test_followup_ending_at_observation_boundary_is_eligible():
    observation_end = START + timedelta(days=14)
    rows = [
        visit(
            "EN1", "P1",
            START + timedelta(days=1),
            observation_end - timedelta(days=7),
        ),
        visit(
            "EN2", "P2",
            START + timedelta(days=1),
            observation_end - timedelta(days=7) + timedelta(minutes=1),
        ),
    ]

    labels = build_representation_labels(rows, START.isoformat(), 336)
    by_id = {row["encounter_id"]: row for row in labels}

    assert by_id["EN1"]["followup_status"] == "eligible"
    assert by_id["EN1"]["seven_day_return"] == 0
    assert by_id["EN2"]["followup_status"] == "censored"
    assert by_id["EN2"]["seven_day_return"] is None
@pytest.mark.parametrize("field", ["encounter_id", "patient_id"])
def test_rejects_missing_ids(field):
    row = visit("EN1", "P1", START, START + timedelta(hours=1))
    row[field] = None

    with pytest.raises(ValueError, match="missing or duplicate"):
        build_representation_labels([row], START.isoformat(), 336)