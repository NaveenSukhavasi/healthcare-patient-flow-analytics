import csv
import json

from edflow.__main__ import main
from edflow.representation_audit import audit_representation


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_v2_cli_writes_reproducible_overlap_safe_runs(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"

    for output in (first, second):
        main([
            "--output", str(output),
            "--hours", "24",
            "--patients", "500",
            "--seed", "7",
            "--generator-version", "2",
            "--return-probability", "0.2",
        ])

    filenames = sorted(path.name for path in first.iterdir())
    assert filenames == sorted(path.name for path in second.iterdir())
    for filename in filenames:
        assert (first / filename).read_bytes() == (
            second / filename
        ).read_bytes()

    manifest = json.loads(
        (first / "manifest.json").read_text(encoding="utf-8")
    )
    encounters = read_csv(first / "encounters.csv")
    snapshots = read_csv(first / "arrival_snapshots.csv")
    event_count = len(
        (first / "events.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    )
    report = audit_representation(
        encounters, manifest["start_at"], manifest["hours"]
    )

    assert manifest["generator_version"] == 2
    assert manifest["return_probability_per_arrival_slot"] == 0.2
    assert manifest["return_window_days"] == 7
    assert manifest["encounter_count"] == len(encounters) > 0
    assert manifest["intentional_return_count"] == (
        len(encounters)
        - len({row["patient_id"] for row in encounters})
    )
    assert len(snapshots) == len(encounters)
    assert event_count == 4 * len(encounters)
    assert report["overlapping_arrivals"] == 0