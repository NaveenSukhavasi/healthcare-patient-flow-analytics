from datetime import datetime, timedelta, timezone

from edflow.representation_audit import audit_representation


START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def visit(
    encounter_id, patient_id, arrival, departure, status="discharged"
):
    return {
        "encounter_id": encounter_id,
        "patient_id": patient_id,
        "arrival_at": arrival.isoformat(),
        "departure_at": departure.isoformat(),
        "departure_status": status,
    }


def test_audit_counts_overlap_returns_and_censoring():
    rows = [
        visit("EN1", "P1", START, START + timedelta(hours=2)),
        visit(
            "EN2", "P1",
            START + timedelta(hours=1),
            START + timedelta(hours=3),
        ),
        visit(
            "EN3", "P1",
            START + timedelta(days=2),
            START + timedelta(days=2, hours=1),
        ),
        visit(
            "EN4", "P1",
            START + timedelta(days=11),
            START + timedelta(days=11, hours=1),
        ),
        visit(
            "EN5", "P2",
            START + timedelta(days=1),
            START + timedelta(days=1, hours=1),
        ),
    ]
    report = audit_representation(rows, START.isoformat(), 336)

    assert report["encounter_count"] == 5
    assert report["patients_with_encounters"] == 2
    assert report["overlapping_arrivals"] == 1
    assert report["eligible_seven_day_followups"] == 4
    assert report["censored_followups"] == 1
    assert report["excluded_admitted_indices"] == 0
    assert report["apparent_seven_day_returns"] == 2
    assert report["apparent_return_rate"] == 0.5


def test_return_exactly_seven_days_after_departure_counts():
    departure = START + timedelta(hours=2)
    rows = [
        visit("EN1", "P1", START, departure),
        visit(
            "EN2", "P1",
            departure + timedelta(days=7),
            departure + timedelta(days=7, hours=1),
        ),
    ]
    report = audit_representation(rows, START.isoformat(), 336)

    assert report["eligible_seven_day_followups"] == 1
    assert report["apparent_seven_day_returns"] == 1


def test_admitted_departure_is_not_an_index_visit():
    rows = [
        visit(
            "EN1", "P1", START, START + timedelta(hours=1),
            status="admitted",
        ),
        visit(
            "EN2", "P1",
            START + timedelta(days=1),
            START + timedelta(days=1, hours=1),
        ),
        visit(
            "EN3", "P2",
            START + timedelta(days=12),
            START + timedelta(days=12, hours=1),
        ),
    ]
    report = audit_representation(rows, START.isoformat(), 336)

    assert report["encounter_count"] == 3
    assert report["excluded_admitted_indices"] == 1
    assert report["eligible_seven_day_followups"] == 1
    assert report["censored_followups"] == 1
    assert report["apparent_seven_day_returns"] == 0