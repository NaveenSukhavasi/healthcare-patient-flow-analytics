import csv
import json
from collections import Counter

import pytest

from edflow.__main__ import main


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_cli_writes_reproducible_linked_files(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"

    for output in (first, second):
        main([
            "--output", str(output),
            "--hours", "3",
            "--patients", "20",
            "--seed", "7",
        ])

    filenames = (
        "patients.csv",
        "events.jsonl",
        "encounters.csv",
        "manifest.json",
    )
    for filename in filenames:
        assert (first / filename).read_bytes() == (
            second / filename
        ).read_bytes()

    patients = read_csv(first / "patients.csv")
    encounters = read_csv(first / "encounters.csv")
    events = [
        json.loads(line)
        for line in (first / "events.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    manifest = json.loads(
        (first / "manifest.json").read_text(encoding="utf-8")
    )

    patient_ids = {patient["patient_id"] for patient in patients}
    encounter_ids = {row["encounter_id"] for row in encounters}
    event_counts = Counter(event["event_type"] for event in events)

    assert len(patients) == 20
    assert len(patient_ids) == 20
    assert len(encounters) > 0
    assert len(encounter_ids) == len(encounters)
    assert all(row["patient_id"] in patient_ids for row in encounters)
    assert all(event["patient_id"] in patient_ids for event in events)
    assert all(event["encounter_id"] in encounter_ids for event in events)

    for event_type in (
        "arrival",
        "triage_completed",
        "treatment_started",
        "departure",
    ):
        assert event_counts[event_type] == len(encounters)

    assert manifest["patient_count"] == 20
    assert manifest["arrival_count"] == len(encounters)
    assert manifest["encounter_count"] == len(encounters)
    assert manifest["event_count"] == len(events)
    assert manifest["hospital_count"] == 8


def test_cli_refuses_to_overwrite_a_run(tmp_path):
    output = tmp_path / "run"
    arguments = [
        "--output", str(output),
        "--hours", "1",
        "--patients", "20",
    ]

    main(arguments)
    original_events = (output / "events.jsonl").read_bytes()
    original_patients = (output / "patients.csv").read_bytes()
    original_encounters = (output / "encounters.csv").read_bytes()

    with pytest.raises(SystemExit):
        main(arguments)

    assert (output / "events.jsonl").read_bytes() == original_events
    assert (output / "patients.csv").read_bytes() == original_patients
    assert (output / "encounters.csv").read_bytes() == original_encounters