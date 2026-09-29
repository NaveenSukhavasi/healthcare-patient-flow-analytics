import argparse
import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .arrivals import DEFAULT_HOSPITALS, generate_arrivals


def utc_datetime(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use an ISO 8601 datetime") from exc

    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise argparse.ArgumentTypeError("start time must include UTC offset +00:00")

    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic ED arrivals")
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

    patient_ids = tuple(
        f"P{number:06d}" for number in range(1, args.patients + 1)
    )
    events = generate_arrivals(
        start_at=args.start,
        hours=args.hours,
        hospitals=DEFAULT_HOSPITALS,
        patient_ids=patient_ids,
        seed=args.seed,
    )

    args.output.mkdir(parents=True, exist_ok=False)

    with (args.output / "events.jsonl").open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event.to_record(), sort_keys=True) + "\n")

    manifest = {
        "start_at": args.start.isoformat(),
        "hours": args.hours,
        "seed": args.seed,
        "patient_count": args.patients,
        "hospital_count": len(DEFAULT_HOSPITALS),
        "hospitals": [asdict(hospital) for hospital in DEFAULT_HOSPITALS],
        "event_count": len(events),
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Generated {len(events)} arrival events in {args.output}")


if __name__ == "__main__":
    main()