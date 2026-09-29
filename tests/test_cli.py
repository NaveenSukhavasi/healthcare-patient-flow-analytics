import csv
import json

import pytest

from edflow.__main__ import main


def read_patients(path):
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

    for filename in ("patients.csv", "events.jsonl", "manifest.json"):
        assert (first / filename).read_bytes() == (
            second / filename
        ).read_bytes()

    patients = read_patients(first / "patients.csv")
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

    assert len(patients) == 20
    assert len(patient_ids) == 20
    assert len(events) > 0
    assert all(event["patient_id"] in patient_ids for event in events)
    assert all(event["event_type"] == "arrival" for event in events)
    assert manifest["patient_count"] == 20
    assert manifest["event_count"] == len(events)
    assert manifest["hospital_count"] == 8


def test_cli_refuses_to_overwrite_a_run(tmp_path):
    output = tmp_path / "run"
    arguments = ["--output", str(output), "--hours", "1", "--patients", "20"]

    main(arguments)
    original_events = (output / "events.jsonl").read_bytes()
    original_patients = (output / "patients.csv").read_bytes()

    with pytest.raises(SystemExit):
        main(arguments)

    assert (output / "events.jsonl").read_bytes() == original_events
    assert (output / "patients.csv").read_bytes() == original_patients