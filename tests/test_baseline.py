from datetime import datetime, timedelta, timezone

from edflow.baseline import evaluate_waiting_time_baselines


def test_chronological_split_excludes_unavailable_labels():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    waits = (10, 20, 100, 1000, 30)
    hospitals = ("H01", "H01", "H02", "H01", "H01")
    training_rows = []
    encounters = []

    for index, (waiting, hospital_id) in enumerate(zip(waits, hospitals)):
        arrival = start + timedelta(hours=index)
        encounter_id = f"EN{index}"
        training_rows.append({
            "encounter_id": encounter_id,
            "arrival_at": arrival.isoformat(),
            "hospital_id": hospital_id,
            "waiting_time_minutes": waiting,
        })
        encounters.append({
            "encounter_id": encounter_id,
            "arrival_at": arrival.isoformat(),
            "hospital_id": hospital_id,
            "treatment_start_at": (
                arrival + timedelta(minutes=waiting)
            ).isoformat(),
        })

    report = evaluate_waiting_time_baselines(training_rows, encounters)

    assert report["split_at_utc"] == (
        start + timedelta(hours=4)
    ).isoformat()
    assert report["training_rows"] == 3
    assert report["excluded_unavailable_labels"] == 1
    assert report["test_rows"] == 1
    assert report["global_median_minutes"] == 20
    assert report["global_median_mae_minutes"] == 10
    assert report["hospital_median_mae_minutes"] == 15