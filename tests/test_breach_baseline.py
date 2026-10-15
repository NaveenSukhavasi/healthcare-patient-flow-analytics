from datetime import datetime, timedelta, timezone

import pytest

from edflow.breach_baseline import evaluate_breach_baseline


def make_records():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    training_rows = []
    encounters = []

    for index in range(5):
        arrival = start + timedelta(hours=12 * index)
        if index == 0:
            departure = arrival + timedelta(hours=4)
        elif index == 3:
            departure = arrival + timedelta(hours=13)
        else:
            departure = arrival + timedelta(hours=5)

        breach = int((departure - arrival).total_seconds() > 4 * 3600)
        encounter_id = f"EN{index}"
        training_rows.append({
            "encounter_id": encounter_id,
            "hospital_id": "H01",
            "arrival_at": arrival.isoformat(),
            "four_hour_breach": breach,
        })
        encounters.append({
            "encounter_id": encounter_id,
            "hospital_id": "H01",
            "arrival_at": arrival.isoformat(),
            "departure_at": departure.isoformat(),
            "four_hour_breach": breach,
        })

    return training_rows, encounters


def test_breach_baseline_excludes_labels_unavailable_at_split():
    training_rows, encounters = make_records()
    report = evaluate_breach_baseline(training_rows, encounters)

    assert report["split_at_utc"] == (
        datetime(2025, 1, 1, tzinfo=timezone.utc)
        + timedelta(hours=48)
    ).isoformat()
    assert report["training_rows"] == 3
    assert report["excluded_unavailable_labels"] == 1
    assert report["test_rows"] == 1
    assert report["training_breach_rate"] == 0.6667
    assert report["test_breach_rate"] == 1.0
    assert report["baseline_brier_score"] == 0.1111


def test_breach_baseline_rejects_incorrect_label():
    training_rows, encounters = make_records()
    training_rows[0]["four_hour_breach"] = 1

    with pytest.raises(ValueError, match="inconsistent breach record"):
        evaluate_breach_baseline(training_rows, encounters)