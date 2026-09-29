from collections import Counter, defaultdict, deque
from datetime import timedelta
from itertools import groupby
from typing import Sequence

from .events import EDEvent, EventType


def build_arrival_snapshots(events: Sequence[EDEvent]) -> list[dict]:
    """Record workload using only events strictly before each arrival."""

    events = tuple(events)
    if len({event.event_id for event in events}) != len(events):
        raise ValueError("duplicate event ID")

    type_order = {
        EventType.ARRIVAL: 0,
        EventType.DEPARTURE: 1,
        EventType.TRIAGE_COMPLETED: 2,
        EventType.TREATMENT_STARTED: 3,
    }
    ordered = sorted(
        events,
        key=lambda event: (
            event.occurred_at,
            type_order[event.event_type],
            event.event_id,
        ),
    )

    # encounter_id -> (hospital_id, patient_id, current_state)
    active = {}
    seen_encounters = set()
    counts = defaultdict(Counter)
    recent_arrivals = defaultdict(deque)
    recent_departures = defaultdict(deque)
    snapshots = []

    for timestamp, grouped_events in groupby(
        ordered, key=lambda event: event.occurred_at
    ):
        group = list(grouped_events)
        cutoff = timestamp - timedelta(hours=1)

        for hospital_id in {event.hospital_id for event in group}:
            for recent in (
                recent_arrivals[hospital_id],
                recent_departures[hospital_id],
            ):
                while recent and recent[0] <= cutoff:
                    recent.popleft()

        # Capture every arrival before applying ANY event at this timestamp.
        for event in group:
            if event.event_type != EventType.ARRIVAL:
                continue

            hospital_id = event.hospital_id
            workload = counts[hospital_id]
            snapshots.append({
                "encounter_id": event.encounter_id,
                "patient_id": event.patient_id,
                "hospital_id": hospital_id,
                "arrival_at": timestamp.isoformat(),
                "untriaged_patients": workload["untriaged"],
                "waiting_for_treatment": workload["waiting"],
                "in_treatment": workload["treating"],
                "arrivals_last_60m": len(recent_arrivals[hospital_id]),
                "departures_last_60m": len(recent_departures[hospital_id]),
            })

        # These changes become visible only to later timestamps.
        for event in group:
            encounter_id = event.encounter_id
            hospital_id = event.hospital_id
            current = active.get(encounter_id)

            if event.event_type == EventType.ARRIVAL:
                if encounter_id in seen_encounters:
                    raise ValueError("duplicate arrival encounter ID")
                seen_encounters.add(encounter_id)
                active[encounter_id] = (
                    hospital_id,
                    event.patient_id,
                    "untriaged",
                )
                counts[hospital_id]["untriaged"] += 1
                recent_arrivals[hospital_id].append(timestamp)
                continue

            if (
                current is None
                or current[0] != hospital_id
                or current[1] != event.patient_id
            ):
                raise ValueError("event does not match an active encounter")

            previous_state = current[2]
            if event.event_type == EventType.TRIAGE_COMPLETED:
                expected_state, next_state = "untriaged", "waiting"
            elif event.event_type == EventType.TREATMENT_STARTED:
                expected_state, next_state = "waiting", "treating"
            elif event.event_type == EventType.DEPARTURE:
                expected_state, next_state = "treating", None
            else:
                raise ValueError("unknown event type")

            if previous_state != expected_state:
                raise ValueError("invalid event sequence")

            counts[hospital_id][previous_state] -= 1
            if next_state is None:
                del active[encounter_id]
                recent_departures[hospital_id].append(timestamp)
            else:
                counts[hospital_id][next_state] += 1
                active[encounter_id] = (
                    hospital_id,
                    event.patient_id,
                    next_state,
                )

    return snapshots