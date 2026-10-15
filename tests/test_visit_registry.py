from datetime import datetime, timedelta, timezone

import pytest

from edflow.visit_registry import VisitRegistry


START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def test_active_patient_cannot_be_assigned_twice():
    registry = VisitRegistry(("P1", "P2"), seed=4, return_probability=0)

    first, first_is_return = registry.assign(START)
    second, second_is_return = registry.assign(START)

    assert first != second
    assert not first_is_return
    assert not second_is_return

    with pytest.raises(ValueError, match="pool exhausted"):
        registry.assign(START + timedelta(hours=1))


def test_discharge_allows_an_intentional_return_after_departure():
    registry = VisitRegistry(("P1",), seed=4, return_probability=1)
    patient_id, _ = registry.assign(START)
    departure = START + timedelta(hours=2)
    registry.release(patient_id, departure, "discharged")

    with pytest.raises(ValueError, match="pool exhausted"):
        registry.assign(departure)

    returning_id, is_return = registry.assign(departure + timedelta(seconds=1))
    assert returning_id == patient_id
    assert is_return


def test_return_at_exactly_seven_days_is_allowed():
    registry = VisitRegistry(("P1",), seed=4, return_probability=1)
    patient_id, _ = registry.assign(START)
    departure = START + timedelta(hours=2)
    registry.release(patient_id, departure, "discharged")

    returning_id, is_return = registry.assign(departure + timedelta(days=7))
    assert returning_id == patient_id
    assert is_return


def test_admission_and_expired_window_do_not_create_returns():
    admitted = VisitRegistry(("P1",), seed=4, return_probability=1)
    patient_id, _ = admitted.assign(START)
    admitted.release(patient_id, START + timedelta(hours=2), "admitted")

    with pytest.raises(ValueError, match="pool exhausted"):
        admitted.assign(START + timedelta(days=1))

    expired = VisitRegistry(("P1",), seed=4, return_probability=1)
    patient_id, _ = expired.assign(START)
    departure = START + timedelta(hours=2)
    expired.release(patient_id, departure, "discharged")

    with pytest.raises(ValueError, match="pool exhausted"):
        expired.assign(departure + timedelta(days=7, seconds=1))


def test_registry_rejects_out_of_order_events():
    registry = VisitRegistry(("P1", "P2"), seed=4, return_probability=0)
    registry.assign(START)

    with pytest.raises(ValueError, match="chronologically"):
        registry.assign(START - timedelta(seconds=1))