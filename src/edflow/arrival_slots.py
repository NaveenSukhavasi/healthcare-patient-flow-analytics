from dataclasses import dataclass
from datetime import datetime, timedelta
from random import Random
from typing import Sequence

from .arrivals import Hospital, _poisson_count


@dataclass(frozen=True, slots=True)
class ArrivalSlot:
    slot_id: str
    hospital_id: str
    occurred_at: datetime
    arrival_mode: str


def generate_arrival_slots(
    *,
    start_at: datetime,
    hours: int,
    hospitals: Sequence[Hospital],
    seed: int,
) -> list[ArrivalSlot]:
    """Generate arrival demand without assigning patient identities."""
    if (
        not isinstance(start_at, datetime)
        or start_at.tzinfo is None
        or start_at.utcoffset() != timedelta(0)
    ):
        raise ValueError("start_at must be a timezone-aware UTC datetime")
    if hours < 1:
        raise ValueError("hours must be positive")

    hospitals = tuple(hospitals)
    if not hospitals:
        raise ValueError("hospitals cannot be empty")
    if len({hospital.hospital_id for hospital in hospitals}) != len(hospitals):
        raise ValueError("hospital IDs must be unique")

    rng = Random(seed)
    candidates = []

    for hour in range(hours):
        hour_start = start_at + timedelta(hours=hour)
        for hospital in hospitals:
            count = _poisson_count(rng, hospital.base_arrivals_per_hour)
            for _ in range(count):
                occurred_at = hour_start + timedelta(seconds=rng.randrange(3600))
                arrival_mode = (
                    "ambulance" if rng.random() < 0.24 else "walk_in"
                )
                candidates.append(
                    (occurred_at, hospital.hospital_id, arrival_mode)
                )

    candidates.sort()
    return [
        ArrivalSlot(
            slot_id=f"AS{number:09d}",
            hospital_id=hospital_id,
            occurred_at=occurred_at,
            arrival_mode=arrival_mode,
        )
        for number, (occurred_at, hospital_id, arrival_mode)
        in enumerate(candidates, start=1)
    ]