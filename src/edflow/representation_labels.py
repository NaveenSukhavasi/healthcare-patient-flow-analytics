from collections import defaultdict
from datetime import datetime, timedelta


FOLLOWUP = timedelta(days=7)


def _utc(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError("timestamps must be UTC")
    return result


def build_representation_labels(encounters, start_at: str, hours: int) -> list[dict]:
    """Label discharged visits with a complete seven-day follow-up window."""
    if hours < 1:
        raise ValueError("hours must be positive")

    observation_start = _utc(start_at)
    observation_end = observation_start + timedelta(hours=hours)
    visits_by_patient = defaultdict(list)
    seen_encounters = set()

    for row in encounters:
        encounter_id = row["encounter_id"]
        patient_id = row["patient_id"]
        if not isinstance(encounter_id, str) or not isinstance(patient_id, str):
            raise ValueError("missing or duplicate encounter or patient ID")
        encounter_id = encounter_id.strip()
        patient_id = patient_id.strip()
        if not encounter_id or encounter_id in seen_encounters or not patient_id:
            raise ValueError("missing or duplicate encounter or patient ID")
        seen_encounters.add(encounter_id)

        arrival = _utc(row["arrival_at"])
        departure = _utc(row["departure_at"])
        status = row["departure_status"]

        if status not in {"discharged", "admitted"}:
            raise ValueError("invalid departure status")
        if not observation_start <= arrival < observation_end:
            raise ValueError("arrival outside observation window")
        if departure < arrival:
            raise ValueError("departure precedes arrival")

        visits_by_patient[patient_id].append(
            (arrival, departure, encounter_id, status)
        )

    labels = []
    for patient_id, visits in visits_by_patient.items():
        visits.sort(key=lambda visit: (visit[0], visit[2]))

        previous_departure = None
        for arrival, departure, _, _ in visits:
            if previous_departure is not None and arrival < previous_departure:
                raise ValueError("overlapping encounters for one patient")
            previous_departure = departure

        for index, (arrival, departure, encounter_id, status) in enumerate(visits):
            followup_end = departure + FOLLOWUP

            if status == "admitted":
                followup_status = "admitted"
                seven_day_return = None
                label_available_at = None
            elif followup_end > observation_end:
                followup_status = "censored"
                seven_day_return = None
                label_available_at = None
            else:
                followup_status = "eligible"
                seven_day_return = int(
                    any(
                        departure < later_arrival <= followup_end
                        for later_arrival, _, _, _ in visits[index + 1:]
                    )
                )
                # Conservative cutoff: both positive and negative labels
                # become available after the full follow-up window.
                label_available_at = followup_end.isoformat()

            labels.append({
                "encounter_id": encounter_id,
                "patient_id": patient_id,
                "arrival_at": arrival.isoformat(),
                "departure_at": departure.isoformat(),
                "followup_status": followup_status,
                "seven_day_return": seven_day_return,
                "label_available_at": label_available_at,
            })

    return sorted(
        labels,
        key=lambda row: (row["arrival_at"], row["encounter_id"]),
    )