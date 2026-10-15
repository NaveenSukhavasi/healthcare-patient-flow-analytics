import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline

from .baseline import evaluate_waiting_time_baselines
from .model_data import FEATURE_COLUMNS


CATEGORICAL_COLUMNS = {"hospital_id", "arrival_mode"}


def arrival_features(row) -> dict:
    return {
        name: row[name] if name in CATEGORICAL_COLUMNS else float(row[name])
        for name in FEATURE_COLUMNS
    }


def evaluate_waiting_time_model(training_rows, encounters) -> dict:
    training_rows = list(training_rows)
    encounters = list(encounters)
    report = evaluate_waiting_time_baselines(training_rows, encounters)
    split_at = datetime.fromisoformat(report["split_at_utc"])
    started_at = {
        row["encounter_id"]: datetime.fromisoformat(row["treatment_start_at"])
        for row in encounters
    }

    train = [
        row for row in training_rows
        if datetime.fromisoformat(row["arrival_at"]) < split_at
        and started_at[row["encounter_id"]] < split_at
    ]
    test = [
        row for row in training_rows
        if datetime.fromisoformat(row["arrival_at"]) >= split_at
    ]
    if len(train) != report["training_rows"] or len(test) != report["test_rows"]:
        raise ValueError("model split differs from reference baseline")

    model = Pipeline([
        ("vectorizer", DictVectorizer(sparse=False)),
        ("regressor", HistGradientBoostingRegressor(
            loss="absolute_error",
            max_iter=150,
            max_leaf_nodes=15,
            min_samples_leaf=20,
            l2_regularization=1.0,
            early_stopping=False,
            random_state=42,
        )),
    ])
    model.fit(
        [arrival_features(row) for row in train],
        [float(row["waiting_time_minutes"]) for row in train],
    )
    predictions = [
        max(0.0, float(value))
        for value in model.predict([arrival_features(row) for row in test])
    ]
    actual = [float(row["waiting_time_minutes"]) for row in test]

    return {
        **report,
        "model": "hist_gradient_boosting_absolute_error",
        "encoded_feature_count": len(
            model.named_steps["vectorizer"].get_feature_names_out()
        ),
        "model_mae_minutes": round(
            float(mean_absolute_error(actual, predictions)), 2
        ),
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate an arrival-time waiting model"
    )
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args(argv)

    def read_csv(filename):
        with (args.run / filename).open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    report = evaluate_waiting_time_model(
        read_csv("arrival_training.csv"),
        read_csv("encounters.csv"),
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()