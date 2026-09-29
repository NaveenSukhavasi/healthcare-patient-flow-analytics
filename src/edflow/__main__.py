import argparse
import csv
import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .arrivals import DEFAULT_HOSPITALS, generate_arrivals
from .events import EventType
from .patients import generate_patients
from .treatment import simulate_treatment
from .triage import generate_triage_events


def utc_datetime(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use an ISO 8601 datetime") from exc

    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise argparse.ArgumentTypeError(
            "start time must include UTC offset +00:00"
        )
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic ED patient flow"
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--start",
        type=utc_datetime,
        default=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--patients", type=int, default=40_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    if args.hours < 1 or args.patients < 1:
        parser.error("hours and patients must be positive")
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")

    patients = generate_patients(
        args.patients,
        seed=args.seed + 1,
        reference_date=args.start.date(),
    )
    arrivals = generate_arrivals(
        start_at=args.start,
        hours=args.hours,
        hospitals=DEFAULT_HOSPITALS,
        patient_ids=tuple(patient.patient_id for patient in patients),
        seed=args.seed,
    )
    triages = generate_triage_events(
        arrivals, patients, seed=args.seed + 2
    )
    treatment_events, encounters = simulate_treatment(
        arrivals,
        triages,
        patients,
        DEFAULT_HOSPITALS,
        seed=args.seed + 3,
    )

    # A departure frees a space before another treatment starts at
    # the same timestamp.
    type_order = {
        EventType.ARRIVAL: 0,
        EventType.DEPARTURE: 1,
        EventType.TRIAGE_COMPLETED: 2,
        EventType.TREATMENT_STARTED: 3,
    }
    events = sorted(
        [*arrivals, *triages, *treatment_events],
        key=lambda event: (
            event.occurred_at,
            type_order[event.event_type],
            event.event_id,
        ),
    )
    encounters.sort(key=lambda row: (row["arrival_at"], row["encounter_id"]))

    args.output.mkdir(parents=True, exist_ok=False)

    with (args.output / "patients.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=tuple(patients[0].to_record()),
        )
        writer.writeheader()
        writer.writerows(patient.to_record() for patient in patients)

    with (args.output / "events.jsonl").open(
        "w", encoding="utf-8"
    ) as handle:
        for event in events:
            handle.write(json.dumps(event.to_record(), sort_keys=True) + "\n")

    encounter_fields = (
        "encounter_id",
        "patient_id",
        "hospital_id",
        "arrival_at",
        "triage_at",
        "triage_category",
        "treatment_start_at",
        "departure_at",
        "departure_status",
        "waiting_time_minutes",
        "ed_length_of_stay_minutes",
        "four_hour_breach",
    )
    with (args.output / "encounters.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=encounter_fields)
        writer.writeheader()
        writer.writerows(encounters)

    manifest = {
        "start_at": args.start.isoformat(),
        "hours": args.hours,
        "arrival_seed": args.seed,
        "patient_seed": args.seed + 1,
        "triage_seed": args.seed + 2,
        "treatment_seed": args.seed + 3,
        "patient_count": len(patients),
        "hospital_count": len(DEFAULT_HOSPITALS),
        "hospitals": [asdict(hospital) for hospital in DEFAULT_HOSPITALS],
        "arrival_count": len(arrivals),
        "encounter_count": len(encounters),
        "event_count": len(events),
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Generated {len(events)} events, {len(encounters)} encounters, "
        f"and {len(patients)} patients in {args.output}"
    )


if __name__ == "__main__":
    main()