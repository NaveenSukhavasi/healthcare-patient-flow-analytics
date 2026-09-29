from datetime import datetime, timedelta, timezone

import pytest

from edflow.events import EDEvent, EventType
from edflow.snapshots import build_arrival_snapshots


BASE = datetime(2025, 1, 1, tzinfo=timezone.utc)


def make_event(event_id, encounter_id, minute, event_type, payload):
    return EDEvent(
        event_id=event_id,
        encounter_id=encounter_id,
        patient_id=f"P-{encounter_id}",
        hospital_id="HX",
        occurred_at=BASE + timedelta(minutes=minute),
        event_type=event_type,
        payload=payload,
    )


def test_snapshots_use_only_strictly_earlier_events():
    events = [
        make_event("A1", "A", 0, EventType.ARRIVAL,
                   {"arrival_mode": "walk_in"}),
        make_event("A2", "A", 1, EventType.TRIAGE_COMPLETED,
                   {"triage_category": 3, "presentation_group": "injury"}),
        make_event("A3", "A", 2, EventType.TREATMENT_STARTED, {}),
        make_event("B1", "B", 5, EventType.ARRIVAL,
                   {"arrival_mode": "ambulance"}),
        make_event("C1", "C", 10, EventType.ARRIVAL,
                   {"arrival_mode": "walk_in"}),
        make_event("A4", "A", 10, EventType.DEPARTURE,
                   {"departure_status": "discharged"}),
        make_event("D1", "D", 11, EventType.ARRIVAL,
                   {"arrival_mode": "walk_in"}),
    ]

    snapshots = build_arrival_snapshots(list(reversed(events)))
    by_encounter = {row["encounter_id"]: row for row in snapshots}

    assert len(snapshots) == 4
    assert by_encounter["A"]["in_treatment"] == 0

    assert by_encounter["B"]["in_treatment"] == 1
    assert by_encounter["B"]["arrivals_last_60m"] == 1

    # A departs at the same instant C arrives. C must not see that departure.
    assert by_encounter["C"]["in_treatment"] == 1
    assert by_encounter["C"]["untriaged_patients"] == 1
    assert by_encounter["C"]["arrivals_last_60m"] == 2
    assert by_encounter["C"]["departures_last_60m"] == 0

    assert by_encounter["D"]["in_treatment"] == 0
    assert by_encounter["D"]["untriaged_patients"] == 2
    assert by_encounter["D"]["arrivals_last_60m"] == 3
    assert by_encounter["D"]["departures_last_60m"] == 1

    assert set(by_encounter["D"]) == {
        "encounter_id",
        "patient_id",
        "hospital_id",
        "arrival_at",
        "untriaged_patients",
        "waiting_for_treatment",
        "in_treatment",
        "arrivals_last_60m",
        "departures_last_60m",
    }


def test_snapshot_rejects_an_event_without_its_arrival():
    triage = make_event(
        "A2", "A", 1, EventType.TRIAGE_COMPLETED,
        {"triage_category": 3, "presentation_group": "injury"},
    )

    with pytest.raises(ValueError, match="active encounter"):
        build_arrival_snapshots([triage])