from datetime import datetime, timedelta, timezone

from edflow.triage_admission_baseline import (
    evaluate_triage_admission_baseline,
)


def test_post_triage_baseline_excludes_unavailable_outcome():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    labels = (0, 1, 1, 0, 1)
    categories = (1, 1, 2, 2, 2)
    training_rows = []
    encounters = []

    for index, (admitted, category) in enumerate(zip(labels, categories)):
        arrival = start + timedelta(hours=index)
        departure = arrival + (
            timedelta(hours=2) if index == 3 else timedelta(minutes=10)
        )
        encounter_id = f"EN{index}"
        training_rows.append({
            "encounter_id": encounter_id,
            "hospital_id": "H01",
            "arrival_at": arrival.isoformat(),
            "admitted_flag": admitted,
        })
        encounters.append({
            "encounter_id": encounter_id,
            "hospital_id": "H01",
            "arrival_at": arrival.isoformat(),
            "triage_at": (arrival + timedelta(minutes=5)).isoformat(),
            "departure_at": departure.isoformat(),
            "triage_category": category,
            "admitted_flag": admitted,
        })

    report = evaluate_triage_admission_baseline(training_rows, encounters)

    assert report["training_rows"] == 3
    assert report["excluded_unavailable_labels"] == 1
    assert report["test_rows"] == 1
    assert report["category_training_counts"] == {"1": 2, "2": 1}
    assert report["category_brier_score"] == 0.0