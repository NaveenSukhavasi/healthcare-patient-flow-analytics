import heapq
from datetime import timedelta
from itertools import count
from random import Random
from typing import Sequence

from .arrivals import Hospital
from .events import EDEvent, EventType
from .patients import Patient


def simulate_treatment(
    arrivals: Sequence[EDEvent],
    triages: Sequence[EDEvent],
    patients: Sequence[Patient],
    hospitals: Sequence[Hospital],
    *,
    seed: int,
) -> tuple[list[EDEvent], list[dict]]:
    """Return treatment/departure events and completed encounter rows."""

    arrivals = tuple(arrivals)
    triages = tuple(triages)
    patients = tuple(patients)
    hospitals = tuple(hospitals)

    arrival_by_id = {event.encounter_id: event for event in arrivals}
    triage_by_id = {event.encounter_id: event for event in triages}
    patient_by_id = {patient.patient_id: patient for patient in patients}
    hospital_by_id = {hospital.hospital_id: hospital for hospital in hospitals}

    if len(arrival_by_id) != len(arrivals):
        raise ValueError("duplicate arrival encounter ID")
    if len(triage_by_id) != len(triages):
        raise ValueError("duplicate triage encounter ID")
    if set(arrival_by_id) != set(triage_by_id):
        raise ValueError("each arrival needs exactly one triage event")
    if len(patient_by_id) != len(patients):
        raise ValueError("duplicate patient ID")
    if len(hospital_by_id) != len(hospitals):
        raise ValueError("duplicate hospital ID")

    for encounter_id, arrival in arrival_by_id.items():
        triage = triage_by_id[encounter_id]
        if arrival.event_type != EventType.ARRIVAL:
            raise ValueError("invalid arrival event")
        if triage.event_type != EventType.TRIAGE_COMPLETED:
            raise ValueError("invalid triage event")
        if (
            arrival.patient_id != triage.patient_id
            or arrival.hospital_id != triage.hospital_id
            or triage.occurred_at < arrival.occurred_at
        ):
            raise ValueError("triage does not match arrival")
        if arrival.patient_id not in patient_by_id:
            raise ValueError("unknown patient")
        if arrival.hospital_id not in hospital_by_id:
            raise ValueError("unknown hospital")

    rng = Random(seed)
    sequence = count()
    schedule = []

    for triage in triages:
        heapq.heappush(
            schedule,
            (triage.occurred_at, 1, next(sequence), triage),
        )

    waiting = {hospital_id: [] for hospital_id in hospital_by_id}
    treating = {hospital_id: set() for hospital_id in hospital_by_id}
    started_at = {}
    new_events = []
    encounters = []

    while schedule:
        current_time = schedule[0][0]
        changed_hospitals = set()

        # Process every event at this time before assigning free spaces.
        while schedule and schedule[0][0] == current_time:
            _, _, _, event = heapq.heappop(schedule)
            hospital_id = event.hospital_id
            encounter_id = event.encounter_id
            changed_hospitals.add(hospital_id)

            if event.event_type == EventType.TRIAGE_COMPLETED:
                heapq.heappush(
                    waiting[hospital_id],
                    (
                        event.payload["triage_category"],
                        event.occurred_at,
                        encounter_id,
                    ),
                )
            else:
                treating[hospital_id].remove(encounter_id)
                new_events.append(event)

                arrival = arrival_by_id[encounter_id]
                triage = triage_by_id[encounter_id]
                start_time = started_at[encounter_id]
                wait_minutes = (
                    start_time - arrival.occurred_at
                ).total_seconds() / 60
                stay_minutes = (
                    event.occurred_at - arrival.occurred_at
                ).total_seconds() / 60

                encounters.append({
                    "encounter_id": encounter_id,
                    "patient_id": arrival.patient_id,
                    "hospital_id": hospital_id,
                    "arrival_at": arrival.occurred_at.isoformat(),
                    "triage_at": triage.occurred_at.isoformat(),
                    "triage_category": triage.payload["triage_category"],
                    "treatment_start_at": start_time.isoformat(),
                    "departure_at": event.occurred_at.isoformat(),
                    "departure_status": event.payload["departure_status"],
                    "waiting_time_minutes": round(wait_minutes, 2),
                    "ed_length_of_stay_minutes": round(stay_minutes, 2),
                    "four_hour_breach": int(stay_minutes > 240),
                    "arrival_mode": arrival.payload["arrival_mode"],
                    "presentation_group": triage.payload["presentation_group"],
                    "admitted_flag": int(event.payload["departure_status"] == "admitted"),
                })

        for hospital_id in sorted(changed_hospitals):
            capacity = hospital_by_id[hospital_id].ed_treatment_spaces

            while waiting[hospital_id] and len(treating[hospital_id]) < capacity:
                category, _, encounter_id = heapq.heappop(
                    waiting[hospital_id]
                )
                arrival = arrival_by_id[encounter_id]
                patient = patient_by_id[arrival.patient_id]

                start_event = EDEvent(
                    event_id=f"{arrival.event_id}-S",
                    encounter_id=encounter_id,
                    patient_id=arrival.patient_id,
                    hospital_id=hospital_id,
                    occurred_at=current_time,
                    event_type=EventType.TREATMENT_STARTED,
                    payload={},
                )
                new_events.append(start_event)
                treating[hospital_id].add(encounter_id)
                started_at[encounter_id] = current_time

                age = patient.age_on(arrival.occurred_at.date())
                base_admission = (0.85, 0.68, 0.38, 0.13, 0.05)[
                    category - 1
                ]
                admission_probability = min(
                    0.97,
                    base_admission
                    + 0.08 * (age >= 75)
                    + 0.04 * patient.chronic_condition_count,
                )
                admitted = rng.random() < admission_probability

                base_minutes = (300, 225, 165, 105, 65)[category - 1]
                duration_minutes = max(
                    20,
                    round(
                        rng.gauss(
                            base_minutes
                            + (100 if admitted else 0)
                            + 12 * patient.chronic_condition_count,
                            30,
                        )
                    ),
                )

                departure = EDEvent(
                    event_id=f"{arrival.event_id}-D",
                    encounter_id=encounter_id,
                    patient_id=arrival.patient_id,
                    hospital_id=hospital_id,
                    occurred_at=current_time + timedelta(
                        minutes=duration_minutes
                    ),
                    event_type=EventType.DEPARTURE,
                    payload={
                        "departure_status": (
                            "admitted" if admitted else "discharged"
                        )
                    },
                )
                heapq.heappush(
                    schedule,
                    (departure.occurred_at, 0, next(sequence), departure),
                )

    return new_events, encounters