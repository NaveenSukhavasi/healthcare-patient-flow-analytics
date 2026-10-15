import csv

from edflow.__main__ import main
from edflow.breach_model import evaluate_breach_model


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_breach_model_evaluates_generated_run(tmp_path):
    output = tmp_path / "run"
    main([
        "--output", str(output),
        "--hours", "24",
        "--patients", "100",
        "--seed", "7",
    ])
    training_rows = read_csv(output / "arrival_training.csv")
    report = evaluate_breach_model(
        training_rows,
        read_csv(output / "encounters.csv"),
    )

    assert (
        report["training_rows"]
        + report["excluded_unavailable_labels"]
        + report["test_rows"]
        == len(training_rows)
    )
    assert report["model"] == "hist_gradient_boosting_classifier"
    assert report["encoded_feature_count"] > 0
    assert 0 <= report["predicted_breach_rate"] <= 1
    assert 0 <= report["model_brier_score"] <= 1