import csv

from edflow.__main__ import main
from edflow.admission_model import evaluate_admission_model


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_admission_model_evaluates_generated_run(tmp_path):
    output = tmp_path / "run"
    main([
        "--output", str(output),
        "--hours", "24",
        "--patients", "100",
        "--seed", "7",
    ])
    training_rows = read_csv(output / "arrival_training.csv")
    report = evaluate_admission_model(
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