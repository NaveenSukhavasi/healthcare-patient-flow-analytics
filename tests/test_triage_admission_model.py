import csv

from edflow.__main__ import main
from edflow.model_data import FEATURE_COLUMNS
from edflow.triage_admission_model import (
    evaluate_triage_admission_model,
    triage_features,
)


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_triage_features_exclude_later_outcomes():
    row = {name: "1" for name in FEATURE_COLUMNS}
    row["hospital_id"] = "H01"
    row["arrival_mode"] = "walk_in"
    encounter = {"triage_category": "2", "admitted_flag": "1"}
    features = triage_features(row, encounter)

    encounter["admitted_flag"] = "0"
    row["waiting_time_minutes"] = "9999"
    row["four_hour_breach"] = "1"

    assert triage_features(row, encounter) == features
    assert set(features) == set(FEATURE_COLUMNS) | {"triage_category"}


def test_triage_model_evaluates_generated_run(tmp_path):
    output = tmp_path / "run"
    main([
        "--output", str(output),
        "--hours", "24",
        "--patients", "100",
        "--seed", "7",
    ])
    training_rows = read_csv(output / "arrival_training.csv")
    report = evaluate_triage_admission_model(
        training_rows,
        read_csv(output / "encounters.csv"),
    )

    assert (
        report["training_rows"]
        + report["excluded_unavailable_labels"]
        + report["test_rows"]
        == len(training_rows)
    )
    assert 0 <= report["predicted_admission_rate"] <= 1
    assert 0 <= report["model_brier_score"] <= 1