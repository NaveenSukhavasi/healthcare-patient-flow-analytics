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
from .snapshots import build_arrival_snapshots
from .analytics import build_hospital_kpis
from .model_data import (FEATURE_COLUMNS,TARGET_COLUMNS,build_arrival_training_rows,)
from .arrival_slots import generate_arrival_slots
from .encounter_rows import build_encounter_rows
from .flow_v2 import generate_event_stream_v2
from .visit_registry import RETURN_WINDOW


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
    parser.add_argument("--generator-version", type=int, choices=(1, 2), default=1)
    parser.add_argument("--return-probability", type=float, default=0.1)
    args = parser.parse_args(argv)

    if args.hours < 1 or args.patients < 1:
        parser.error("hours and patients must be positive")
    if not 0 <= args.return_probability <= 1:
        parser.error("return probability must be between 0 and 1")
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")

    patients = generate_patients(
        args.patients,
        seed=args.seed + 1,
        reference_date=args.start.date(),
    )
    if args.generator_version == 1:
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
    else:
        slots = generate_arrival_slots(
            start_at=args.start,
            hours=args.hours,
            hospitals=DEFAULT_HOSPITALS,
            seed=args.seed,
        )
        events = generate_event_stream_v2(
            slots,
            patients,
            DEFAULT_HOSPITALS,
            seed=args.seed,
            return_probability=args.return_probability,
        )
        arrivals = [
            event for event in events
            if event.event_type == EventType.ARRIVAL
        ]
        encounters = build_encounter_rows(events)

    snapshots = build_arrival_snapshots(events)

    encounters.sort(key=lambda row: (row["arrival_at"], row["encounter_id"]))

    hospital_kpis, daily_kpis = build_hospital_kpis(encounters)

    training_rows = build_arrival_training_rows(encounters,snapshots,[patient.to_record() for patient in patients],)

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
        "arrival_mode",
        "triage_at",
        "triage_category",
        "presentation_group",
        "treatment_start_at",
        "departure_at",
        "departure_status",
        "admitted_flag",
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

    hospital_fields = (
        "hospital_id",
        "presentation_count",
        "median_waiting_time_minutes",
        "median_ed_length_of_stay_minutes",
        "four_hour_completion_rate",
        "admission_rate",
    )
    daily_fields = (
        "hospital_id",
        "arrival_date_utc",
        *hospital_fields[1:],
    )
    for filename, fields, rows in (
        ("hospital_kpis.csv", hospital_fields, hospital_kpis),
        ("hospital_daily_kpis.csv", daily_fields, daily_kpis),
    ):
        with (args.output / filename).open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    training_fields = ("encounter_id","arrival_at",*FEATURE_COLUMNS,*TARGET_COLUMNS,)

    with (args.output / "arrival_training.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=training_fields)
        writer.writeheader()
        writer.writerows(training_rows)

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
        "snapshot_count": len(snapshots),
        "hospital_kpi_count": len(hospital_kpis),
        "daily_kpi_count": len(daily_kpis),
        "training_row_count": len(training_rows),
        "generator_version": args.generator_version,
    }
    if args.generator_version == 2:
        manifest.update({
            "registry_seed": args.seed + 1,
            "return_probability_per_arrival_slot": args.return_probability,
            "return_window_days": RETURN_WINDOW.days,
            "intentional_return_count": (
                len(encounters)
                - len({row["patient_id"] for row in encounters})
            ),
        })
    snapshot_fields = (
        "encounter_id",
        "patient_id",
        "hospital_id",
        "arrival_at",
        "untriaged_patients",
        "waiting_for_treatment",
        "in_treatment",
        "arrivals_last_60m",
        "departures_last_60m",
    )
    with (args.output / "arrival_snapshots.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=snapshot_fields)
        writer.writeheader()
        writer.writerows(snapshots)
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