from datetime import datetime, timedelta
from random import Random
from typing import Sequence


RETURN_WINDOW = timedelta(days=7)


class VisitRegistry:
    """Assign patients to chronological arrivals without overlapping visits."""

    def __init__(
        self,
        patient_ids: Sequence[str],
        *,
        seed: int,
        return_probability: float,
    ) -> None:
        ids = tuple(patient_ids)
        if not ids or any(not isinstance(pid, str) or not pid.strip() for pid in ids):
            raise ValueError("patient IDs must be non-empty strings")
        if len(set(ids)) != len(ids):
            raise ValueError("patient IDs must be unique")
        if not 0 <= return_probability <= 1:
            raise ValueError("return_probability must be between 0 and 1")

        self._rng = Random(seed)
        self._new_patients = list(ids)
        self._active: dict[str, datetime] = {}
        self._discharged: dict[str, datetime] = {}
        self._return_probability = return_probability
        self._last_event_at: datetime | None = None

    def _check_time(self, occurred_at: datetime) -> None:
        if (
            not isinstance(occurred_at, datetime)
            or occurred_at.tzinfo is None
            or occurred_at.utcoffset() != timedelta(0)
        ):
            raise ValueError("event time must be a timezone-aware UTC datetime")
        if self._last_event_at is not None and occurred_at < self._last_event_at:
            raise ValueError("registry events must be processed chronologically")

    def assign(self, arrival_at: datetime) -> tuple[str, bool]:
        """Return (patient_id, is_intentional_return) for an arrival."""
        self._check_time(arrival_at)

        eligible_returns = sorted(
            patient_id
            for patient_id, departed_at in self._discharged.items()
            if departed_at < arrival_at <= departed_at + RETURN_WINDOW
        )

        choose_return = (
            bool(eligible_returns)
            and self._rng.random() < self._return_probability
        )

        if choose_return:
            patient_id = self._rng.choice(eligible_returns)
            del self._discharged[patient_id]
        elif self._new_patients:
            index = self._rng.randrange(len(self._new_patients))
            patient_id = self._new_patients[index]
            self._new_patients[index] = self._new_patients[-1]
            self._new_patients.pop()
        else:
            raise ValueError(
                "patient pool exhausted at the configured return probability"
            )

        self._active[patient_id] = arrival_at
        self._last_event_at = arrival_at
        return patient_id, choose_return

    def release(
        self,
        patient_id: str,
        departure_at: datetime,
        departure_status: str,
    ) -> None:
        """End an active ED encounter and make discharged patients returnable."""
        self._check_time(departure_at)
        if departure_status not in {"discharged", "admitted"}:
            raise ValueError("invalid departure status")
        if patient_id not in self._active:
            raise ValueError("patient has no active encounter")
        if departure_at < self._active[patient_id]:
            raise ValueError("departure precedes arrival")

        del self._active[patient_id]
        if departure_status == "discharged":
            self._discharged[patient_id] = departure_at

        self._last_event_at = departure_at