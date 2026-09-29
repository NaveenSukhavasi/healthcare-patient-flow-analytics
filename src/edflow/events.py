from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping


class EventType(StrEnum):
    ARRIVAL = "arrival"
    TRIAGE_COMPLETED = "triage_completed"
    TREATMENT_STARTED = "treatment_started"
    DEPARTURE = "departure"


_REQUIRED_FIELDS = {
    EventType.ARRIVAL: {"arrival_mode"},
    EventType.TRIAGE_COMPLETED: {"triage_category", "presentation_group"},
    EventType.TREATMENT_STARTED: set(),
    EventType.DEPARTURE: {"departure_status"},
}


@dataclass(frozen=True, slots=True)
class EDEvent:
    event_id: str
    encounter_id: str
    patient_id: str
    hospital_id: str
    occurred_at: datetime
    event_type: EventType
    payload: Mapping[str, str | int]
    schema_version: int = 1

    def __post_init__(self) -> None:
        for name in ("event_id", "encounter_id", "patient_id", "hospital_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} cannot be empty")

        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() != timedelta(0):
            raise ValueError("occurred_at must be a timezone-aware UTC datetime")

        if not isinstance(self.event_type, EventType):
            raise TypeError("event_type must be an EventType")

        if self.schema_version != 1:
            raise ValueError("unsupported schema_version")

        if set(self.payload) != _REQUIRED_FIELDS[self.event_type]:
            raise ValueError(f"invalid payload fields for {self.event_type.value}")

        if self.event_type == EventType.ARRIVAL:
            if self.payload["arrival_mode"] not in {"walk_in", "ambulance"}:
                raise ValueError("invalid arrival_mode")

        if self.event_type == EventType.TRIAGE_COMPLETED:
            category = self.payload["triage_category"]
            if type(category) is not int or category not in range(1, 6):
                raise ValueError("triage_category must be an integer from 1 to 5")
            if not str(self.payload["presentation_group"]).strip():
                raise ValueError("presentation_group cannot be empty")

        if self.event_type == EventType.DEPARTURE:
            if self.payload["departure_status"] not in {"admitted", "discharged"}:
                raise ValueError("invalid departure_status")

        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

    def to_record(self) -> dict:
        return {
            "event_id": self.event_id,
            "encounter_id": self.encounter_id,
            "patient_id": self.patient_id,
            "hospital_id": self.hospital_id,
            "occurred_at": self.occurred_at.isoformat(),
            "event_type": self.event_type.value,
            "payload": dict(self.payload),
            "schema_version": self.schema_version,
        }