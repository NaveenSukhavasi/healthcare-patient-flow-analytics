from dataclasses import dataclass
from datetime import datetime, timedelta
from math import exp
from random import Random
from typing import Sequence

from .events import EDEvent, EventType


@dataclass(frozen=True, slots=True)
class Hospital:
    hospital_id: str
    hospital_name: str
    region: str
    bed_capacity: int
    ed_treatment_spaces: int
    base_arrivals_per_hour: float

    def __post_init__(self) -> None:
        if not self.hospital_id.strip() or not self.hospital_name.strip():
            raise ValueError("hospital ID and name cannot be empty")
        if self.bed_capacity < 1 or self.ed_treatment_spaces < 1:
            raise ValueError("hospital capacities must be positive")
        if self.base_arrivals_per_hour <= 0:
            raise ValueError("arrival rate must be positive")


# Fictional hospitals and illustrative rates, not real service data.
DEFAULT_HOSPITALS = (
    Hospital("H01", "Yarra Central", "metropolitan", 520, 8, 1.60),
    Hospital("H02", "Northern Plains", "metropolitan", 430, 7, 1.40),
    Hospital("H03", "Bayview", "metropolitan", 350, 6, 1.20),
    Hospital("H04", "Westgate", "metropolitan", 320, 6, 1.10),
    Hospital("H05", "Goldfields Regional", "regional", 230, 5, 1.00),
    Hospital("H06", "Gippsland Regional", "regional", 200, 5, 0.85),
    Hospital("H07", "Mallee District", "rural", 110, 4, 0.70),
    Hospital("H08", "Highlands District", "rural", 90, 4, 0.60),
)


def _poisson_count(rng: Random, rate: float) -> int:
    """Sample a count for one hour from a Poisson distribution."""
    threshold = exp(-rate)
    product = 1.0
    count = 0

    while product > threshold:
        count += 1
        product *= rng.random()

    return count - 1


def generate_arrivals(
    *,
    start_at: datetime,
    hours: int,
    hospitals: Sequence[Hospital],
    patient_ids: Sequence[str],
    seed: int,
) -> list[EDEvent]:
    """Generate chronological synthetic arrival events."""

    if start_at.tzinfo is None or start_at.utcoffset() != timedelta(0):
        raise ValueError("start_at must be a timezone-aware UTC datetime")
    if hours < 1:
        raise ValueError("hours must be positive")

    hospitals = tuple(hospitals)
    patient_ids = tuple(patient_ids)

    if not hospitals or not patient_ids:
        raise ValueError("hospitals and patient_ids cannot be empty")
    if len({h.hospital_id for h in hospitals}) != len(hospitals):
        raise ValueError("hospital IDs must be unique")
    if any(not isinstance(pid, str) or not pid.strip() for pid in patient_ids):
        raise ValueError("patient IDs must be non-empty strings")
    if len(set(patient_ids)) != len(patient_ids):
        raise ValueError("patient IDs must be unique")

    rng = Random(seed)
    candidates = []

    for hour in range(hours):
        hour_start = start_at + timedelta(hours=hour)

        for hospital in hospitals:
            count = _poisson_count(rng, hospital.base_arrivals_per_hour)

            for _ in range(count):
                occurred_at = hour_start + timedelta(seconds=rng.randrange(3600))
                patient_id = rng.choice(patient_ids)
                arrival_mode = (
                    "ambulance" if rng.random() < 0.24 else "walk_in"
                )
                candidates.append(
                    (occurred_at, hospital.hospital_id, patient_id, arrival_mode)
                )

    candidates.sort()

    return [
        EDEvent(
            event_id=f"EV{number:09d}",
            encounter_id=f"EN{number:09d}",
            patient_id=patient_id,
            hospital_id=hospital_id,
            occurred_at=occurred_at,
            event_type=EventType.ARRIVAL,
            payload={"arrival_mode": arrival_mode},
        )
        for number, (occurred_at, hospital_id, patient_id, arrival_mode)
        in enumerate(candidates, start=1)
    ]