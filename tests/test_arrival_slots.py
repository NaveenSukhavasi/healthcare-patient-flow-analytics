from datetime import datetime, timedelta, timezone

import pytest

from edflow.arrival_slots import generate_arrival_slots
from edflow.arrivals import DEFAULT_HOSPITALS


START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def test_slots_are_reproducible_ordered_and_have_no_patient_id():
    settings = {
        "start_at": START,
        "hours": 24,
        "hospitals": DEFAULT_HOSPITALS[:2],
        "seed": 42,
    }
    first = generate_arrival_slots(**settings)
    second = generate_arrival_slots(**settings)

    assert first == second
    assert first
    assert [slot.occurred_at for slot in first] == sorted(
        slot.occurred_at for slot in first
    )
    assert len({slot.slot_id for slot in first}) == len(first)
    assert all(
        START <= slot.occurred_at < START + timedelta(hours=24)
        and slot.hospital_id in {"H01", "H02"}
        and slot.arrival_mode in {"ambulance", "walk_in"}
        and not hasattr(slot, "patient_id")
        for slot in first
    )


def test_slots_reject_naive_start_time():
    with pytest.raises(ValueError, match="UTC"):
        generate_arrival_slots(
            start_at=datetime(2025, 1, 1),
            hours=24,
            hospitals=DEFAULT_HOSPITALS,
            seed=42,
        )