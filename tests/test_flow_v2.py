from datetime import date, datetime, timedelta, timezone

import pytest

from edflow.arrival_slots import ArrivalSlot
from edflow.arrivals import Hospital
from edflow.events import EventType
from edflow.flow_v2 import generate_event_stream_v2
from edflow.patients import generate_patients
from edflow.treatment_outcomes import TreatmentOutcome, TreatmentOutcomeSampler


START = datetime(2025, 1, 1, tzinfo=timezone.utc)
HOSPITAL = Hospital("HX", "Test Hospital", "regional", 100, 1, 4.0)


def slot(number: int, minutes: int) -> ArrivalSlot:
    return ArrivalSlot(
        f"S{number}",
        "HX",
        START + timedelta(minutes=minutes),
        "walk_in",
    )


def test_v2_return_follows_departure_and_respects_capacity(monkeypatch):
    def discharge_after_20(
        self, patient, *, triage_category, arrival_at
    ):
        return TreatmentOutcome("discharged", 20)

    monkeypatch.setattr(
        TreatmentOutcomeSampler, "sample", discharge_after_20
    )
    patients = generate_patients(
        2, seed=21, reference_date=date(2025, 1, 1)
    )
    events = generate_event_stream_v2(
        (slot(1, 0), slot(2, 1), slot(3, 60)),
        patients,
        (HOSPITAL,),
        seed=22,
        return_probability=1.0,
    )

    arrivals = [
        event for event in events if event.event_type == EventType.ARRIVAL
    ]
    departures = {
        event.encounter_id: event
        for event in events
        if event.event_type == EventType.DEPARTURE
    }

    assert len(arrivals) == 3
    assert len({event.patient_id for event in arrivals[:2]}) == 2
    assert arrivals[2].patient_id in {
        event.patient_id for event in arrivals[:2]
    }
    earlier_visit = next(
        event for event in arrivals[:2]
        if event.patient_id == arrivals[2].patient_id
    )
    assert (
        departures[earlier_visit.encounter_id].occurred_at
        < arrivals[2].occurred_at
    )

    active_treatments = 0
    for event in events:
        if event.event_type == EventType.TREATMENT_STARTED:
            active_treatments += 1
        elif event.event_type == EventType.DEPARTURE:
            active_treatments -= 1
        assert 0 <= active_treatments <= HOSPITAL.ed_treatment_spaces
    assert active_treatments == 0


def test_v2_refuses_to_reuse_a_patient_still_in_ed():
    patients = generate_patients(
        1, seed=21, reference_date=date(2025, 1, 1)
    )
    with pytest.raises(ValueError, match="patient pool exhausted"):
        generate_event_stream_v2(
            (slot(1, 0), slot(2, 1)),
            patients,
            (HOSPITAL,),
            seed=22,
            return_probability=1.0,
        )