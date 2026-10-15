import csv

from edflow.__main__ import main
from edflow.model_data import FEATURE_COLUMNS
from edflow.waiting_model import arrival_features, evaluate_waiting_time_model


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_model_features_exclude_future_information():
    row = {name: "1" for name in FEATURE_COLUMNS}
    row["hospital_id"] = "H01"
    row["arrival_mode"] = "walk_in"
    features = arrival_features(row)

    row.update({
        "waiting_time_minutes": "9999",
        "admitted_flag": "1",
        "four_hour_breach": "1",
        "triage_category": "1",
        "departure_status": "admitted",
    })

    assert arrival_features(row) == features
    assert set(features) == set(FEATURE_COLUMNS)


def test_model_evaluates_generated_run(tmp_path):
    output = tmp_path / "run"
    main([
        "--output", str(output),
        "--hours", "24",
        "--patients", "100",
        "--seed", "7",
    ])
    training_rows = read_csv(output / "arrival_training.csv")
    report = evaluate_waiting_time_model(
        training_rows,
        read_csv(output / "encounters.csv"),
    )

    assert (
        report["training_rows"]
        + report["excluded_unavailable_labels"]
        + report["test_rows"]
        == len(training_rows)
    )
    assert report["model_mae_minutes"] >= 0
    assert sum(group["count"] for group in report["by_arrival_mode"].values()) == report["test_rows"]
    assert sum(group["count"] for group in report["by_hospital"].values()) == report["test_rows"]
