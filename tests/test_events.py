from datetime import datetime, timezone

import pytest

from edflow.events import EDEvent, EventType


def make_event(**changes):
    values = {
        "event_id": "EV001",
        "encounter_id": "EN001",
        "patient_id": "P001",
        "hospital_id": "H001",
        "occurred_at": datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        "event_type": EventType.ARRIVAL,
        "payload": {"arrival_mode": "walk_in"},
    }
    values.update(changes)
    return EDEvent(**values)


def test_valid_arrival_can_be_serialized():
    record = make_event().to_record()

    assert record["event_type"] == "arrival"
    assert record["occurred_at"] == "2025-01-01T10:00:00+00:00"
    assert record["payload"] == {"arrival_mode": "walk_in"}
    assert record["schema_version"] == 1


def test_arrival_rejects_future_outcome_fields():
    with pytest.raises(ValueError, match="invalid payload fields"):
        make_event(
            payload={
                "arrival_mode": "walk_in",
                "departure_status": "admitted",
            }
        )


def test_event_requires_utc_timestamp():
    with pytest.raises(ValueError, match="UTC"):
        make_event(occurred_at=datetime(2025, 1, 1, 10, 0))


def test_triage_category_must_be_valid():
    with pytest.raises(ValueError, match="triage_category"):
        make_event(
            event_type=EventType.TRIAGE_COMPLETED,
            payload={"triage_category": 6, "presentation_group": "injury"},
        )


def test_payload_cannot_change_after_event_creation():
    original = {"arrival_mode": "walk_in"}
    event = make_event(payload=original)

    original["arrival_mode"] = "ambulance"
    assert event.payload["arrival_mode"] == "walk_in"

    with pytest.raises(TypeError):
        event.payload["arrival_mode"] = "ambulance"