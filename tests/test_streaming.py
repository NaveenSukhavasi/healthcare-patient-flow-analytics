import sqlite3
from datetime import datetime, timezone

import pytest

from edflow.events import EDEvent, EventType
from edflow.streaming import (
    initialise_store,
    store_record,
    validate_record,
)


def arrival_record():
    return EDEvent(
        event_id="EV1",
        encounter_id="EN1",
        patient_id="P1",
        hospital_id="H01",
        occurred_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        event_type=EventType.ARRIVAL,
        payload={"arrival_mode": "walk_in"},
    ).to_record()


def test_stream_validation_rejects_invalid_payload():
    record = arrival_record()
    record["payload"] = {"arrival_mode": "invalid"}
    with pytest.raises(ValueError, match="arrival_mode"):
        validate_record(record)


def test_sqlite_sink_is_idempotent_and_rejects_conflicts():
    connection = sqlite3.connect(":memory:")
    initialise_store(connection)
    record = arrival_record()

    assert store_record(connection, record)
    assert not store_record(connection, record)
    assert connection.execute(
        "SELECT COUNT(*) FROM ed_events"
    ).fetchone()[0] == 1

    conflicting = dict(record)
    conflicting["patient_id"] = "P2"
    with pytest.raises(ValueError, match="conflicting"):
        store_record(connection, conflicting)

    connection.close()