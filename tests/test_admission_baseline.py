from datetime import datetime, timedelta, timezone

from edflow.admission_baseline import evaluate_admission_baseline


def test_admission_baseline_excludes_labels_unavailable_at_split():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    labels = (0, 1, 1, 0, 1)
    training_rows = []
    encounters = []

    for index, admitted in enumerate(labels):
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
            "departure_at": departure.isoformat(),
            "admitted_flag": admitted,
        })

    report = evaluate_admission_baseline(training_rows, encounters)

    assert report["split_at_utc"] == (start + timedelta(hours=4)).isoformat()
    assert report["training_rows"] == 3
    assert report["excluded_unavailable_labels"] == 1
    assert report["test_rows"] == 1
    assert report["training_admission_rate"] == 0.6667
    assert report["baseline_brier_score"] == 0.1111