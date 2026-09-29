from datetime import datetime, timedelta, timezone

import pytest

from edflow.arrivals import DEFAULT_HOSPITALS, generate_arrivals
from edflow.events import EventType


START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def test_arrivals_are_reproducible_ordered_and_valid():
    settings = {
        "start_at": START,
        "hours": 24,
        "hospitals": DEFAULT_HOSPITALS[:2],
        "patient_ids": ("P001", "P002", "P003"),
        "seed": 42,
    }

    first = generate_arrivals(**settings)
    second = generate_arrivals(**settings)

    assert len(first) > 0
    assert [event.to_record() for event in first] == [
        event.to_record() for event in second
    ]
    assert [event.occurred_at for event in first] == sorted(
        event.occurred_at for event in first
    )
    assert len({event.event_id for event in first}) == len(first)
    assert all(
        START <= event.occurred_at < START + timedelta(hours=24)
        for event in first
    )
    assert all(
        event.event_type == EventType.ARRIVAL
        and set(event.payload) == {"arrival_mode"}
        for event in first
    )


def test_naive_start_time_is_rejected():
    with pytest.raises(ValueError, match="UTC"):
        generate_arrivals(
            start_at=datetime(2025, 1, 1),
            hours=24,
            hospitals=DEFAULT_HOSPITALS,
            patient_ids=("P001",),
            seed=42,
        )