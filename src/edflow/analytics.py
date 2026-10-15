from collections import defaultdict
from datetime import datetime, timedelta
from statistics import median
from typing import Iterable, Mapping


def _utc_datetime(value: str, field: str) -> datetime:
    try:
        result = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"invalid {field}") from exc

    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be UTC")
    return result


def _summarize(rows: list[dict]) -> dict:
    count = len(rows)
    return {
        "presentation_count": count,
        "median_waiting_time_minutes": round(
            median(row["wait"] for row in rows), 2
        ),
        "median_ed_length_of_stay_minutes": round(
            median(row["stay"] for row in rows), 2
        ),
        "four_hour_completion_rate": round(
            1 - sum(row["breach"] for row in rows) / count, 4
        ),
        "admission_rate": round(
            sum(row["admitted"] for row in rows) / count, 4
        ),
    }


def build_hospital_kpis(
    encounters: Iterable[Mapping],
) -> tuple[list[dict], list[dict]]:
    """Validate completed encounters and return hospital and UTC-day KPIs."""

    by_hospital = defaultdict(list)
    by_hospital_day = defaultdict(list)
    seen_ids = set()

    for row in encounters:
        encounter_id = str(row["encounter_id"]).strip()
        hospital_id = str(row["hospital_id"]).strip()
        if not encounter_id or not hospital_id:
            raise ValueError("encounter_id and hospital_id are required")
        if encounter_id in seen_ids:
            raise ValueError("duplicate encounter ID")
        seen_ids.add(encounter_id)

        arrival = _utc_datetime(row["arrival_at"], "arrival_at")
        triage = _utc_datetime(row["triage_at"], "triage_at")
        start = _utc_datetime(
            row["treatment_start_at"], "treatment_start_at"
        )
        departure = _utc_datetime(row["departure_at"], "departure_at")
        if not arrival <= triage <= start <= departure:
            raise ValueError("invalid encounter timestamp order")

        if row["arrival_mode"] not in {"walk_in", "ambulance"}:
            raise ValueError("invalid arrival_mode")
        if int(row["triage_category"]) not in range(1, 6):
            raise ValueError("invalid triage_category")
        if not str(row["presentation_group"]).strip():
            raise ValueError("presentation_group is required")

        wait = (start - arrival).total_seconds() / 60
        stay = (departure - arrival).total_seconds() / 60
        if abs(float(row["waiting_time_minutes"]) - round(wait, 2)) > 0.001:
            raise ValueError("incorrect waiting_time_minutes")
        if abs(
            float(row["ed_length_of_stay_minutes"]) - round(stay, 2)
        ) > 0.001:
            raise ValueError("incorrect ed_length_of_stay_minutes")

        breach = int(row["four_hour_breach"])
        if breach != int(stay > 240):
            raise ValueError("incorrect four_hour_breach")

        status = row["departure_status"]
        if status not in {"admitted", "discharged"}:
            raise ValueError("invalid departure_status")
        admitted = int(row["admitted_flag"])
        if admitted != int(status == "admitted"):
            raise ValueError("incorrect admitted_flag")

        metrics = {
            "wait": wait,
            "stay": stay,
            "breach": breach,
            "admitted": admitted,
        }
        by_hospital[hospital_id].append(metrics)
        by_hospital_day[
            (hospital_id, arrival.date().isoformat())
        ].append(metrics)

    hospital_rows = [
        {"hospital_id": hospital_id, **_summarize(rows)}
        for hospital_id, rows in sorted(by_hospital.items())
    ]
    daily_rows = [
        {
            "hospital_id": hospital_id,
            "arrival_date_utc": date,
            **_summarize(rows),
        }
        for (hospital_id, date), rows in sorted(by_hospital_day.items())
    ]
    return hospital_rows, daily_rows