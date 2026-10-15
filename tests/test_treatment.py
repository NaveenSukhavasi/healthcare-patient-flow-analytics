from datetime import date, datetime, timezone

from edflow.arrivals import Hospital, generate_arrivals
from edflow.events import EventType
from edflow.patients import generate_patients
from edflow.treatment import simulate_treatment
from edflow.triage import generate_triage_events


def sample_flow():
    hospital = Hospital(
        "HX", "Test Hospital", "regional", 100, 1, 4.0
    )
    patients = generate_patients(
        100, seed=21, reference_date=date(2025, 1, 1)
    )
    arrivals = generate_arrivals(
        start_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        hours=6,
        hospitals=(hospital,),
        patient_ids=[patient.patient_id for patient in patients],
        seed=22,
    )
    triages = generate_triage_events(arrivals, patients, seed=23)
    return hospital, patients, arrivals, triages


def test_treatment_respects_capacity_and_completes_encounters():
    hospital, patients, arrivals, triages = sample_flow()
    events, encounters = simulate_treatment(
        arrivals, triages, patients, (hospital,), seed=24
    )

    assert len(events) == 2 * len(arrivals)
    assert len(encounters) == len(arrivals)
    arrival_by_id = {event.encounter_id: event for event in arrivals}
    triage_by_id = {event.encounter_id: event for event in triages}

    for row in encounters:
        encounter_id = row["encounter_id"]
        assert row["arrival_mode"] == (
            arrival_by_id[encounter_id].payload["arrival_mode"]
        )
        assert row["presentation_group"] == (
            triage_by_id[encounter_id].payload["presentation_group"]
        )
        assert row["admitted_flag"] == int(
            row["departure_status"] == "admitted"
        )

    active = 0
    for event in events:
        if event.event_type == EventType.TREATMENT_STARTED:
            active += 1
        else:
            assert event.event_type == EventType.DEPARTURE
            active -= 1
        assert 0 <= active <= hospital.ed_treatment_spaces

    assert active == 0
    assert any(row["waiting_time_minutes"] > 15 for row in encounters)
    assert all(row["ed_length_of_stay_minutes"] > 0 for row in encounters)


def test_same_seed_produces_same_treatment_outcomes():
    hospital, patients, arrivals, triages = sample_flow()

    first_events, first_rows = simulate_treatment(
        arrivals, triages, patients, (hospital,), seed=24
    )
    second_events, second_rows = simulate_treatment(
        arrivals, triages, patients, (hospital,), seed=24
    )

    assert [event.to_record() for event in first_events] == [
        event.to_record() for event in second_events
    ]
    assert first_rows == second_rows