from datetime import datetime

from edflow.__main__ import main as generate_run
from edflow.representation_model import evaluate_run


def test_representation_model_uses_available_labels_and_future_holdout(
    tmp_path,
):
    run = tmp_path / "weighted-28d"
    generate_run([
        "--output", str(run),
        "--start", "2025-01-01T00:00:00+00:00",
        "--hours", "672",
        "--patients", "15000",
        "--seed", "42",
        "--generator-version", "2",
        "--return-probability", "0.1",
        "--return-risk-weighting",
    ])

    report = evaluate_run(run)

    split = datetime.fromisoformat(report["split_at_utc"])
    latest_training_label = datetime.fromisoformat(
        report["latest_training_label_at_utc"]
    )
    earliest_test_departure = datetime.fromisoformat(
        report["earliest_test_departure_at_utc"]
    )

    assert report["return_selection"] == (
        "chronic_condition_weighted_v1"
    )
    assert report["training_rows"] > 100
    assert report["test_rows"] > 100
    assert report["purged_pre_split_rows"] > 0
    assert latest_training_label <= split
    assert earliest_test_departure >= split
    assert 0 <= report["baseline"]["brier_score"] <= 1
    assert 0 <= report["model"]["brier_score"] <= 1