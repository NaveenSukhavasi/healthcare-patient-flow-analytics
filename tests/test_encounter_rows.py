from datetime import date, datetime, timedelta, timezone

import pytest

from edflow.arrival_slots import ArrivalSlot
from edflow.arrivals import Hospital
from edflow.encounter_rows import build_encounter_rows
from edflow.events import EDEvent, EventType
from edflow.flow_v2 import generate_event_stream_v2
from edflow.patients import generate_patients
from edflow.representation_audit import audit_representation
from edflow.treatment_outcomes import TreatmentOutcome, TreatmentOutcomeSampler


START = datetime(2025, 1, 1, tzinfo=timezone.utc)
HOSPITAL = Hospital("HX", "Test Hospital", "regional", 100, 1, 4.0)


def test_v2_rows_show_a_return_without_overlapping_visits(monkeypatch):
    def discharge_after_20(
        self, patient, *, triage_category, arrival_at
    ):
        return TreatmentOutcome("discharged", 20)

    monkeypatch.setattr(
        TreatmentOutcomeSampler, "sample", discharge_after_20
    )
    patients = generate_patients(
        1, seed=21, reference_date=date(2025, 1, 1)
    )
    slots = (
        ArrivalSlot("S1", "HX", START, "walk_in"),
        ArrivalSlot("S2", "HX", START + timedelta(hours=1), "ambulance"),
    )
    events = generate_event_stream_v2(
        slots,
        patients,
        (HOSPITAL,),
        seed=22,
        return_probability=1.0,
    )
    rows = build_encounter_rows(events)
    report = audit_representation(rows, START.isoformat(), 336)

    assert len(rows) == 2
    assert rows[0]["patient_id"] == rows[1]["patient_id"]
    assert rows[0]["departure_at"] < rows[1]["arrival_at"]
    assert [row["arrival_mode"] for row in rows] == [
        "walk_in", "ambulance"
    ]
    assert report["overlapping_arrivals"] == 0
    assert report["apparent_seven_day_returns"] == 1


def test_rows_reject_an_incomplete_encounter():
    arrival = EDEvent(
        event_id="EV1",
        encounter_id="EN1",
        patient_id="P1",
        hospital_id="HX",
        occurred_at=START,
        event_type=EventType.ARRIVAL,
        payload={"arrival_mode": "walk_in"},
    )
    with pytest.raises(ValueError, match="requires one arrival"):
        build_encounter_rows((arrival,))