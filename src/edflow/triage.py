from datetime import timedelta
from random import Random
from typing import Sequence

from .events import EDEvent, EventType
from .patients import Patient


class TriageSampler:
    """Keep one random stream across successive arrivals."""

    def __init__(self, *, seed: int) -> None:
        self._rng = Random(seed)

    def sample(self, arrival: EDEvent, patient: Patient) -> EDEvent:
        if arrival.event_type != EventType.ARRIVAL:
            raise ValueError("input must be an arrival event")
        if arrival.patient_id != patient.patient_id:
            raise ValueError("patient does not match arrival")

        age = patient.age_on(arrival.occurred_at.date())
        ambulance = arrival.payload["arrival_mode"] == "ambulance"

        category_weights = (
            (3, 20, 45, 27, 5)
            if ambulance
            else (1, 8, 35, 45, 11)
        )
        category = self._rng.choices(
            (1, 2, 3, 4, 5),
            weights=category_weights,
        )[0]

        if patient.chronic_condition_count >= 3 and self._rng.random() < 0.20:
            category = max(1, category - 1)

        groups = (
            "respiratory",
            "injury",
            "cardiac",
            "gastrointestinal",
            "other",
        )
        group_weights = (
            (30, 10, 28, 15, 17)
            if age >= 65
            else (18, 32, 8, 20, 22)
        )
        presentation_group = self._rng.choices(
            groups,
            weights=group_weights,
        )[0]

        triage_at = arrival.occurred_at + timedelta(
            minutes=self._rng.randint(3, 15)
        )

        return EDEvent(
            event_id=f"{arrival.event_id}-T",
            encounter_id=arrival.encounter_id,
            patient_id=arrival.patient_id,
            hospital_id=arrival.hospital_id,
            occurred_at=triage_at,
            event_type=EventType.TRIAGE_COMPLETED,
            payload={
                "triage_category": category,
                "presentation_group": presentation_group,
            },
        )


def generate_triage_events(
    arrivals: Sequence[EDEvent],
    patients: Sequence[Patient],
    *,
    seed: int,
) -> list[EDEvent]:
    """Create one later triage event for each arrival."""
    arrivals = tuple(arrivals)
    patients = tuple(patients)
    patient_by_id = {patient.patient_id: patient for patient in patients}

    if len(patient_by_id) != len(patients):
        raise ValueError("patient IDs must be unique")
    if len({event.event_id for event in arrivals}) != len(arrivals):
        raise ValueError("arrival event IDs must be unique")

    sampler = TriageSampler(seed=seed)
    triage_events = []

    for arrival in arrivals:
        patient = patient_by_id.get(arrival.patient_id)
        if patient is None:
            raise ValueError(f"unknown patient: {arrival.patient_id}")
        triage_events.append(sampler.sample(arrival, patient))

    return sorted(
        triage_events,
        key=lambda event: (event.occurred_at, event.event_id),
    )