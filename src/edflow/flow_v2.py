import heapq
from datetime import datetime, timedelta
from itertools import count
from typing import Sequence

from .arrival_slots import ArrivalSlot
from .arrivals import Hospital
from .events import EDEvent, EventType
from .patients import Patient
from .treatment_outcomes import TreatmentOutcomeSampler
from .triage import TriageSampler
from .visit_registry import VisitRegistry


def generate_event_stream_v2(
    slots: Sequence[ArrivalSlot],
    patients: Sequence[Patient],
    hospitals: Sequence[Hospital],
    *,
    seed: int,
    return_probability: float,
    return_risk_weighting: bool = False,
) -> list[EDEvent]:
    """Process arrival slots, triage and departures in chronological order."""
    slots = tuple(slots)
    patients = tuple(patients)
    hospitals = tuple(hospitals)

    if not hospitals:
        raise ValueError("hospitals cannot be empty")
    hospital_by_id = {hospital.hospital_id: hospital for hospital in hospitals}
    if len(hospital_by_id) != len(hospitals):
        raise ValueError("hospital IDs must be unique")
    if len({slot.slot_id for slot in slots}) != len(slots):
        raise ValueError("slot IDs must be unique")
    if any(slot.hospital_id not in hospital_by_id for slot in slots):
        raise ValueError("arrival slot has an unknown hospital")
    for slot in slots:
        if (
            not isinstance(slot.occurred_at, datetime)
            or slot.occurred_at.tzinfo is None
            or slot.occurred_at.utcoffset() != timedelta(0)
        ):
            raise ValueError("slot time must be a timezone-aware UTC datetime")

    slots = tuple(sorted(slots, key=lambda slot: (slot.occurred_at, slot.slot_id)))
    number_by_slot = {
        slot.slot_id: number for number, slot in enumerate(slots, start=1)
    }
    patient_by_id = {patient.patient_id: patient for patient in patients}
    registry = VisitRegistry(
        tuple(patient.patient_id for patient in patients),
        seed=seed + 1,
        return_probability=return_probability,
        return_weights=(
            {
                patient.patient_id: 1.0 + 2.0 * patient.chronic_condition_count
                for patient in patients
            }
            if return_risk_weighting
            else None
        ),
    )
    triage_sampler = TriageSampler(seed=seed + 2)
    outcome_sampler = TreatmentOutcomeSampler(seed=seed + 3)

    sequence = count()
    schedule = []
    for slot in slots:
        heapq.heappush(
            schedule, (slot.occurred_at, 1, next(sequence), slot)
        )

    waiting = {hospital_id: [] for hospital_id in hospital_by_id}
    treating = {hospital_id: set() for hospital_id in hospital_by_id}
    arrival_by_id = {}
    events = []

    while schedule:
        current_time = schedule[0][0]
        changed_hospitals = set()

        # Departures are processed before arrivals at the same timestamp.
        while schedule and schedule[0][0] == current_time:
            _, _, _, item = heapq.heappop(schedule)

            if isinstance(item, ArrivalSlot):
                patient_id, _ = registry.assign(item.occurred_at)
                patient = patient_by_id[patient_id]
                number = number_by_slot[item.slot_id]
                arrival = EDEvent(
                    event_id=f"EV{number:09d}",
                    encounter_id=f"EN{number:09d}",
                    patient_id=patient_id,
                    hospital_id=item.hospital_id,
                    occurred_at=item.occurred_at,
                    event_type=EventType.ARRIVAL,
                    payload={"arrival_mode": item.arrival_mode},
                )
                arrival_by_id[arrival.encounter_id] = arrival
                events.append(arrival)

                triage = triage_sampler.sample(arrival, patient)
                heapq.heappush(
                    schedule,
                    (triage.occurred_at, 2, next(sequence), triage),
                )

            elif item.event_type == EventType.DEPARTURE:
                treating[item.hospital_id].remove(item.encounter_id)
                registry.release(
                    item.patient_id,
                    item.occurred_at,
                    item.payload["departure_status"],
                )
                events.append(item)
                changed_hospitals.add(item.hospital_id)

            elif item.event_type == EventType.TRIAGE_COMPLETED:
                events.append(item)
                heapq.heappush(
                    waiting[item.hospital_id],
                    (
                        item.payload["triage_category"],
                        item.occurred_at,
                        item.encounter_id,
                    ),
                )
                changed_hospitals.add(item.hospital_id)

        # Start treatment only after all events at this timestamp are handled.
        for hospital_id in sorted(changed_hospitals):
            capacity = hospital_by_id[hospital_id].ed_treatment_spaces
            while waiting[hospital_id] and len(treating[hospital_id]) < capacity:
                category, _, encounter_id = heapq.heappop(
                    waiting[hospital_id]
                )
                arrival = arrival_by_id[encounter_id]
                patient = patient_by_id[arrival.patient_id]

                start = EDEvent(
                    event_id=f"{arrival.event_id}-S",
                    encounter_id=encounter_id,
                    patient_id=arrival.patient_id,
                    hospital_id=hospital_id,
                    occurred_at=current_time,
                    event_type=EventType.TREATMENT_STARTED,
                    payload={},
                )
                events.append(start)
                treating[hospital_id].add(encounter_id)

                outcome = outcome_sampler.sample(
                    patient,
                    triage_category=category,
                    arrival_at=arrival.occurred_at,
                )
                departure = EDEvent(
                    event_id=f"{arrival.event_id}-D",
                    encounter_id=encounter_id,
                    patient_id=arrival.patient_id,
                    hospital_id=hospital_id,
                    occurred_at=current_time + timedelta(
                        minutes=outcome.duration_minutes
                    ),
                    event_type=EventType.DEPARTURE,
                    payload={
                        "departure_status": outcome.departure_status
                    },
                )
                heapq.heappush(
                    schedule,
                    (departure.occurred_at, 0, next(sequence), departure),
                )

    type_order = {
        EventType.ARRIVAL: 0,
        EventType.DEPARTURE: 1,
        EventType.TRIAGE_COMPLETED: 2,
        EventType.TREATMENT_STARTED: 3,
    }
    return sorted(
        events,
        key=lambda event: (
            event.occurred_at,
            type_order[event.event_type],
            event.event_id,
        ),
    )