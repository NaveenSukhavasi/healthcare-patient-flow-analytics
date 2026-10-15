from datetime import date, datetime, timedelta
from typing import Iterable, Mapping


FEATURE_COLUMNS = (
    "hospital_id",
    "arrival_mode",
    "age_years",
    "chronic_condition_count",
    "hour_utc",
    "day_of_week_utc",
    "is_weekend_utc",
    "untriaged_patients",
    "waiting_for_treatment",
    "in_treatment",
    "arrivals_last_60m",
    "departures_last_60m",
)

TARGET_COLUMNS = (
    "waiting_time_minutes",
    "admitted_flag",
    "four_hour_breach",
)

WORKLOAD_COLUMNS = (
    "untriaged_patients",
    "waiting_for_treatment",
    "in_treatment",
    "arrivals_last_60m",
    "departures_last_60m",
)


def _index(rows: Iterable[Mapping], key: str) -> dict:
    indexed = {}
    for row in rows:
        value = str(row[key]).strip()
        if not value or value in indexed:
            raise ValueError(f"missing or duplicate {key}")
        indexed[value] = row
    return indexed


def build_arrival_training_rows(
    encounters: Iterable[Mapping],
    snapshots: Iterable[Mapping],
    patients: Iterable[Mapping],
) -> list[dict]:
    """Join completed labels to features known at each arrival."""

    encounter_by_id = _index(encounters, "encounter_id")
    snapshot_by_id = _index(snapshots, "encounter_id")
    patient_by_id = _index(patients, "patient_id")

    if set(encounter_by_id) != set(snapshot_by_id):
        raise ValueError("each encounter needs one arrival snapshot")

    rows = []
    for encounter_id, encounter in encounter_by_id.items():
        snapshot = snapshot_by_id[encounter_id]
        if any(
            encounter[field] != snapshot[field]
            for field in ("patient_id", "hospital_id", "arrival_at")
        ):
            raise ValueError("snapshot does not match encounter")

        patient = patient_by_id.get(encounter["patient_id"])
        if patient is None:
            raise ValueError("unknown patient")

        arrival = datetime.fromisoformat(encounter["arrival_at"])
        if arrival.tzinfo is None or arrival.utcoffset() != timedelta(0):
            raise ValueError("arrival_at must be UTC")

        birth = date.fromisoformat(patient["birth_date"])
        age = (
            arrival.year
            - birth.year
            - (
                (arrival.month, arrival.day)
                < (birth.month, birth.day)
            )
        )
        if age < 0:
            raise ValueError("birth date is after arrival")

        if encounter["arrival_mode"] not in {"walk_in", "ambulance"}:
            raise ValueError("invalid arrival_mode")

        workload = {
            name: int(snapshot[name]) for name in WORKLOAD_COLUMNS
        }
        if any(value < 0 for value in workload.values()):
            raise ValueError("negative arrival workload")

        waiting = float(encounter["waiting_time_minutes"])
        admitted = int(encounter["admitted_flag"])
        breach = int(encounter["four_hour_breach"])
        if waiting < 0 or admitted not in (0, 1) or breach not in (0, 1):
            raise ValueError("invalid target")

        rows.append({
            "encounter_id": encounter_id,
            "arrival_at": arrival.isoformat(),
            "hospital_id": encounter["hospital_id"],
            "arrival_mode": encounter["arrival_mode"],
            "age_years": age,
            "chronic_condition_count": int(
                patient["chronic_condition_count"]
            ),
            "hour_utc": arrival.hour,
            "day_of_week_utc": arrival.weekday(),
            "is_weekend_utc": int(arrival.weekday() >= 5),
            **workload,
            "waiting_time_minutes": waiting,
            "admitted_flag": admitted,
            "four_hour_breach": breach,
        })

    return sorted(
        rows,
        key=lambda row: (row["arrival_at"], row["encounter_id"]),
    )