from dataclasses import dataclass
from datetime import datetime
from random import Random

from .patients import Patient


@dataclass(frozen=True, slots=True)
class TreatmentOutcome:
    departure_status: str
    duration_minutes: int


class TreatmentOutcomeSampler:
    def __init__(self, *, seed: int) -> None:
        self._rng = Random(seed)

    def sample(
        self,
        patient: Patient,
        *,
        triage_category: int,
        arrival_at: datetime,
    ) -> TreatmentOutcome:
        if triage_category not in range(1, 6):
            raise ValueError("triage_category must be 1 to 5")

        age = patient.age_on(arrival_at.date())
        base_admission = (0.85, 0.68, 0.38, 0.13, 0.05)[
            triage_category - 1
        ]
        admission_probability = min(
            0.97,
            base_admission
            + 0.08 * (age >= 75)
            + 0.04 * patient.chronic_condition_count,
        )
        admitted = self._rng.random() < admission_probability

        base_minutes = (300, 225, 165, 105, 65)[triage_category - 1]
        duration_minutes = max(
            20,
            round(
                self._rng.gauss(
                    base_minutes
                    + (100 if admitted else 0)
                    + 12 * patient.chronic_condition_count,
                    30,
                )
            ),
        )
        return TreatmentOutcome(
            departure_status="admitted" if admitted else "discharged",
            duration_minutes=duration_minutes,
        )