from dataclasses import dataclass
from datetime import date, timedelta
from random import Random


@dataclass(frozen=True, slots=True)
class Patient:
    patient_id: str
    birth_date: date
    sex: str
    indigenous_status: str
    socioeconomic_quintile: int
    remoteness: str
    chronic_condition_count: int

    def __post_init__(self) -> None:
        if not self.patient_id.strip():
            raise ValueError("patient_id cannot be empty")
        if self.sex not in {"female", "male", "unknown"}:
            raise ValueError("invalid sex")
        if self.indigenous_status not in {"yes", "no", "unknown"}:
            raise ValueError("invalid indigenous_status")
        if self.socioeconomic_quintile not in range(1, 6):
            raise ValueError("socioeconomic_quintile must be 1 to 5")
        if self.remoteness not in {"metropolitan", "regional", "rural"}:
            raise ValueError("invalid remoteness")
        if self.chronic_condition_count not in range(0, 6):
            raise ValueError("chronic_condition_count must be 0 to 5")

    def age_on(self, encounter_date: date) -> int:
        if encounter_date < self.birth_date:
            raise ValueError("encounter date precedes birth date")
        return (
            encounter_date.year
            - self.birth_date.year
            - (
                (encounter_date.month, encounter_date.day)
                < (self.birth_date.month, self.birth_date.day)
            )
        )

    def to_record(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "birth_date": self.birth_date.isoformat(),
            "sex": self.sex,
            "indigenous_status": self.indigenous_status,
            "socioeconomic_quintile": self.socioeconomic_quintile,
            "remoteness": self.remoteness,
            "chronic_condition_count": self.chronic_condition_count,
        }


def generate_patients(
    count: int, *, seed: int, reference_date: date
) -> list[Patient]:
    if count < 1:
        raise ValueError("count must be positive")

    rng = Random(seed)
    age_bands = ((0, 17), (18, 39), (40, 64), (65, 84), (85, 100))
    band_weights = (18, 27, 29, 20, 6)
    patients = []

    for number in range(1, count + 1):
        lower, upper = rng.choices(age_bands, weights=band_weights)[0]
        sampled_age = rng.randint(lower, upper)
        birth_date = reference_date - timedelta(
            days=round((sampled_age + rng.random()) * 365.2425)
        )

        age = (
            reference_date.year
            - birth_date.year
            - (
                (reference_date.month, reference_date.day)
                < (birth_date.month, birth_date.day)
            )
        )

        if age < 18:
            chronic_probability = 0.05
        elif age < 40:
            chronic_probability = 0.15
        elif age < 65:
            chronic_probability = 0.35
        else:
            chronic_probability = 0.65

        chronic_count = sum(
            rng.random() < chronic_probability for _ in range(5)
        )

        patients.append(
            Patient(
                patient_id=f"P{number:06d}",
                birth_date=birth_date,
                sex=rng.choices(
                    ("female", "male", "unknown"),
                    weights=(49.5, 49.5, 1),
                )[0],
                indigenous_status=rng.choices(
                    ("yes", "no", "unknown"),
                    weights=(3, 94, 3),
                )[0],
                socioeconomic_quintile=rng.randint(1, 5),
                remoteness=rng.choices(
                    ("metropolitan", "regional", "rural"),
                    weights=(70, 25, 5),
                )[0],
                chronic_condition_count=chronic_count,
            )
        )

    return patients