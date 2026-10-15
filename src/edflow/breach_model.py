import argparse
import csv
import json
from pathlib import Path

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.pipeline import Pipeline

from .admission_baseline import _utc
from .breach_baseline import evaluate_breach_baseline
from .waiting_model import arrival_features


def evaluate_breach_model(training_rows, encounters):
    training_rows = list(training_rows)
    encounters = list(encounters)
    report = evaluate_breach_baseline(training_rows, encounters)
    split_at = _utc(report["split_at_utc"])
    departed_at = {
        row["encounter_id"]: _utc(row["departure_at"])
        for row in encounters
    }

    train = [
        row for row in training_rows
        if _utc(row["arrival_at"]) < split_at
        and departed_at[row["encounter_id"]] < split_at
    ]
    test = [
        row for row in training_rows
        if _utc(row["arrival_at"]) >= split_at
    ]
    if len(train) != report["training_rows"] or len(test) != report["test_rows"]:
        raise ValueError("model split differs from breach baseline")

    train_labels = [int(row["four_hour_breach"]) for row in train]
    if set(train_labels) != {0, 1}:
        raise ValueError("training split needs both breach classes")

    model = Pipeline([
        ("vectorizer", DictVectorizer(sparse=False)),
        ("classifier", HistGradientBoostingClassifier(
            max_iter=150,
            max_leaf_nodes=15,
            min_samples_leaf=20,
            l2_regularization=1.0,
            early_stopping=False,
            random_state=42,
        )),
    ])
    model.fit([arrival_features(row) for row in train], train_labels)

    probabilities = model.predict_proba(
        [arrival_features(row) for row in test]
    )[:, 1]
    actual = [int(row["four_hour_breach"]) for row in test]

    return {
        **report,
        "model": "hist_gradient_boosting_classifier",
        "encoded_feature_count": len(
            model.named_steps["vectorizer"].get_feature_names_out()
        ),
        "predicted_breach_rate": round(
            float(sum(probabilities) / len(probabilities)), 4
        ),
        "model_brier_score": round(
            float(sum(
                (label - probability) ** 2
                for label, probability in zip(actual, probabilities)
            ) / len(actual)),
            4,
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Evaluate an arrival-time four-hour breach model"
    )
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args(argv)

    def read_csv(filename):
        with (args.run / filename).open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    report = evaluate_breach_model(
        read_csv("arrival_training.csv"),
        read_csv("encounters.csv"),
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()