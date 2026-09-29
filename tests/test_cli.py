import json

import pytest

from edflow.__main__ import main


def test_cli_writes_reproducible_arrival_files(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"

    for output in (first, second):
        main([
            "--output", str(output),
            "--hours", "3",
            "--patients", "20",
            "--seed", "7",
        ])

    assert (first / "events.jsonl").read_bytes() == (
        second / "events.jsonl"
    ).read_bytes()

    events = [
        json.loads(line)
        for line in (first / "events.jsonl").read_text(
            encoding="utf-8"
        ).splitlines()
    ]
    manifest = json.loads(
        (first / "manifest.json").read_text(encoding="utf-8")
    )

    assert len(events) > 0
    assert manifest["event_count"] == len(events)
    assert manifest["hospital_count"] == 8
    assert all(event["event_type"] == "arrival" for event in events)


def test_cli_refuses_to_overwrite_a_run(tmp_path):
    output = tmp_path / "run"
    arguments = ["--output", str(output), "--hours", "1", "--patients", "20"]

    main(arguments)
    original = (output / "events.jsonl").read_bytes()

    with pytest.raises(SystemExit):
        main(arguments)

    assert (output / "events.jsonl").read_bytes() == original