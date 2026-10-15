import argparse
import csv
import json
from pathlib import Path

from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .admission_baseline import _utc
from .triage_admission_baseline import evaluate_triage_admission_baseline
from .waiting_model import arrival_features


def triage_features(row, encounter):
    return {
        **arrival_features(row),
        "triage_category": str(int(encounter["triage_category"])),
    }


def evaluate_triage_admission_model(training_rows, encounters):
    training_rows = list(training_rows)
    encounters = list(encounters)
    report = evaluate_triage_admission_baseline(training_rows, encounters)
    split_at = _utc(report["split_at_utc"])
    encounter_by_id = {row["encounter_id"]: row for row in encounters}

    train = [
        row for row in training_rows
        if _utc(row["arrival_at"]) < split_at
        and _utc(encounter_by_id[row["encounter_id"]]["departure_at"]) < split_at
    ]
    test = [
        row for row in training_rows
        if _utc(row["arrival_at"]) >= split_at
    ]
    if len(train) != report["training_rows"] or len(test) != report["test_rows"]:
        raise ValueError("model split differs from triage baseline")

    labels = [int(row["admitted_flag"]) for row in train]
    if set(labels) != {0, 1}:
        raise ValueError("training split needs both admission classes")

    model = Pipeline([
        ("vectorizer", DictVectorizer(sparse=False)),
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=1000)),
    ])
    model.fit(
        [triage_features(row, encounter_by_id[row["encounter_id"]])
         for row in train],
        labels,
    )

    probabilities = model.predict_proba(
        [triage_features(row, encounter_by_id[row["encounter_id"]])
         for row in test]
    )[:, 1]
    actual = [int(row["admitted_flag"]) for row in test]

    return {
        **report,
        "model": "regularized_logistic_regression",
        "encoded_feature_count": len(
            model.named_steps["vectorizer"].get_feature_names_out()
        ),
        "predicted_admission_rate": round(
            float(sum(probabilities) / len(probabilities)), 4
        ),
        "model_brier_score": round(
            float(sum((label - probability) ** 2
                      for label, probability in zip(actual, probabilities))
                  / len(actual)),
            4,
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Evaluate a post-triage admission model"
    )
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args(argv)

    def read_csv(filename):
        with (args.run / filename).open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    report = evaluate_triage_admission_model(
        read_csv("arrival_training.csv"),
        read_csv("encounters.csv"),
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()