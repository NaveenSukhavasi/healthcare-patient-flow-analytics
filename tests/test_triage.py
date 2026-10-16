from datetime import date, datetime, timedelta, timezone

import pytest

from edflow.arrivals import DEFAULT_HOSPITALS, generate_arrivals
from edflow.events import EventType
from edflow.patients import generate_patients
from edflow.triage import TriageSampler, generate_triage_events

START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def sample_data():
    patients = generate_patients(
        100, seed=11, reference_date=date(2025, 1, 1)
    )
    arrivals = generate_arrivals(
        start_at=START,
        hours=4,
        hospitals=DEFAULT_HOSPITALS[:2],
        patient_ids=[patient.patient_id for patient in patients],
        seed=12,
    )
    return patients, arrivals


def test_triage_follows_arrival_and_is_reproducible():
    patients, arrivals = sample_data()
    first = generate_triage_events(arrivals, patients, seed=13)
    second = generate_triage_events(arrivals, patients, seed=13)
    arrival_by_encounter = {
        event.encounter_id: event for event in arrivals
    }

    assert len(first) == len(arrivals)
    assert [event.to_record() for event in first] == [
        event.to_record() for event in second
    ]
    assert len({event.event_id for event in first}) == len(first)
    assert [event.occurred_at for event in first] == sorted(
        event.occurred_at for event in first
    )

    for triage in first:
        arrival = arrival_by_encounter[triage.encounter_id]

        assert triage.event_type == EventType.TRIAGE_COMPLETED
        assert triage.patient_id == arrival.patient_id
        assert triage.hospital_id == arrival.hospital_id
        assert arrival.occurred_at < triage.occurred_at
        assert triage.occurred_at <= arrival.occurred_at + timedelta(
            minutes=15
        )
        assert triage.payload["triage_category"] in range(1, 6)
        assert set(arrival.payload) == {"arrival_mode"}


def test_missing_patient_is_rejected():
    patients, arrivals = sample_data()

    with pytest.raises(ValueError, match="unknown patient"):
        generate_triage_events(arrivals, patients[:1], seed=13)

def test_incremental_triage_matches_batch():
    patients, arrivals = sample_data()
    patient_by_id = {patient.patient_id: patient for patient in patients}
    sampler = TriageSampler(seed=13)

    incremental = [
        sampler.sample(arrival, patient_by_id[arrival.patient_id])
        for arrival in arrivals
    ]
    batch = generate_triage_events(arrivals, patients, seed=13)

    assert sorted(
        (event.to_record() for event in incremental),
        key=lambda record: (record["occurred_at"], record["event_id"]),
    ) == [event.to_record() for event in batch]