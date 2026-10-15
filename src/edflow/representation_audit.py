import argparse
import csv
import json
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from .admission_baseline import _utc


FOLLOWUP = timedelta(days=7)


def audit_representation(encounters, start_at, hours):
    start = _utc(start_at)
    if hours < 1:
        raise ValueError("hours must be positive")
    observation_end = start + timedelta(hours=hours)

    visits_by_patient = defaultdict(list)
    seen_encounters = set()
    encounter_count = 0

    for row in encounters:
        encounter_id = row["encounter_id"]
        patient_id = row["patient_id"]
        if not encounter_id or encounter_id in seen_encounters or not patient_id:
            raise ValueError("missing or duplicate encounter or patient ID")
        seen_encounters.add(encounter_id)

        arrival = _utc(row["arrival_at"])
        departure = _utc(row["departure_at"])
        if not start <= arrival < observation_end or departure < arrival:
            raise ValueError("encounter outside observation window or invalid order")

        visits_by_patient[patient_id].append((arrival, departure, encounter_id))
        encounter_count += 1

    overlapping_arrivals = 0
    eligible_followups = 0
    apparent_returns = 0

    for visits in visits_by_patient.values():
        visits.sort()
        active_until = None

        for arrival, departure, _ in visits:
            if active_until is not None and arrival < active_until:
                overlapping_arrivals += 1
            active_until = (
                departure if active_until is None
                else max(active_until, departure)
            )

        for index, (_, departure, _) in enumerate(visits):
            followup_end = departure + FOLLOWUP
            if followup_end > observation_end:
                continue

            eligible_followups += 1
            if any(
                departure < later_arrival <= followup_end
                for later_arrival, _, _ in visits[index + 1:]
            ):
                apparent_returns += 1

    return {
        "observation_end_utc": observation_end.isoformat(),
        "encounter_count": encounter_count,
        "patients_with_encounters": len(visits_by_patient),
        "overlapping_arrivals": overlapping_arrivals,
        "eligible_seven_day_followups": eligible_followups,
        "censored_followups": encounter_count - eligible_followups,
        "apparent_seven_day_returns": apparent_returns,
        "apparent_return_rate": (
            round(apparent_returns / eligible_followups, 4)
            if eligible_followups else None
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Audit synthetic seven-day re-presentation data"
    )
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args(argv)

    with (args.run / "manifest.json").open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    with (args.run / "encounters.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        encounters = list(csv.DictReader(handle))

    report = audit_representation(
        encounters,
        manifest["start_at"],
        int(manifest["hours"]),
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()