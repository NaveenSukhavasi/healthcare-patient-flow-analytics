from typing import Sequence

from .events import EDEvent, EventType


def build_encounter_rows(events: Sequence[EDEvent]) -> list[dict]:
    """Build one completed encounter row from each set of four events."""
    by_encounter: dict[str, dict[EventType, EDEvent]] = {}
    seen_event_ids = set()

    for event in events:
        if event.event_id in seen_event_ids:
            raise ValueError("duplicate event ID")
        seen_event_ids.add(event.event_id)

        visit = by_encounter.setdefault(event.encounter_id, {})
        if event.event_type in visit:
            raise ValueError("duplicate event type for encounter")
        visit[event.event_type] = event

    completed = []
    for encounter_id, visit in by_encounter.items():
        if set(visit) != set(EventType):
            raise ValueError(
                "encounter requires one arrival, triage, treatment start, "
                "and departure"
            )

        arrival = visit[EventType.ARRIVAL]
        triage = visit[EventType.TRIAGE_COMPLETED]
        start = visit[EventType.TREATMENT_STARTED]
        departure = visit[EventType.DEPARTURE]

        if len({
            (event.patient_id, event.hospital_id)
            for event in visit.values()
        }) != 1:
            raise ValueError("encounter events disagree on patient or hospital")
        if not (
            arrival.occurred_at < triage.occurred_at
            <= start.occurred_at < departure.occurred_at
        ):
            raise ValueError("encounter events are out of order")

        wait_minutes = (
            start.occurred_at - arrival.occurred_at
        ).total_seconds() / 60
        stay_minutes = (
            departure.occurred_at - arrival.occurred_at
        ).total_seconds() / 60
        status = departure.payload["departure_status"]

        row = {
            "encounter_id": encounter_id,
            "patient_id": arrival.patient_id,
            "hospital_id": arrival.hospital_id,
            "arrival_at": arrival.occurred_at.isoformat(),
            "triage_at": triage.occurred_at.isoformat(),
            "triage_category": triage.payload["triage_category"],
            "treatment_start_at": start.occurred_at.isoformat(),
            "departure_at": departure.occurred_at.isoformat(),
            "departure_status": status,
            "waiting_time_minutes": round(wait_minutes, 2),
            "ed_length_of_stay_minutes": round(stay_minutes, 2),
            "four_hour_breach": int(stay_minutes > 240),
            "arrival_mode": arrival.payload["arrival_mode"],
            "presentation_group": triage.payload["presentation_group"],
            "admitted_flag": int(status == "admitted"),
        }
        completed.append((arrival.occurred_at, encounter_id, row))

    return [row for _, _, row in sorted(completed)]