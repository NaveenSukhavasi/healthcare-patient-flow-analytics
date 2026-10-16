"""Export a synthetic run as small JSON snapshots for a static dashboard."""

import argparse
import csv
import json
from collections import deque
from pathlib import Path

from .dashboard import load_run
from .representation_audit import audit_representation


EVENT_FIELDS = (
    "event_id",
    "encounter_id",
    "hospital_id",
    "occurred_at",
    "event_type",
)


def export_run(run: Path, out: Path) -> None:
    data = load_run(run)
    manifest = data["manifest"]
    if manifest.get("generator_version") != 2:
        raise ValueError("static dashboard requires a version-two run")

    with (run / "encounters.csv").open(newline="", encoding="utf-8") as handle:
        encounters = list(csv.DictReader(handle))
    representation = {
        "available": True,
        **audit_representation(
            encounters, manifest["start_at"], int(manifest["hours"])
        ),
    }
    if representation["overlapping_arrivals"]:
        raise ValueError("run contains overlapping patient arrivals")

    recent_events = deque(maxlen=12)
    with (run / "events.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                event = json.loads(line)
                recent_events.append({field: event[field] for field in EVENT_FIELDS})

    payloads = {
        "manifest": manifest,
        "hospitals": data["hospitals"],
        "daily": data["daily"],
        "representation": representation,
        "events": list(reversed(recent_events)),
    }
    out.mkdir(parents=True, exist_ok=True)
    for name, payload in payloads.items():
        (out / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    export_run(args.run, args.out)


if __name__ == "__main__":
    main()
