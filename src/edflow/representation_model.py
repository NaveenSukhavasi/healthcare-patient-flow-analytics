import argparse
import csv
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction import DictVectorizer
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline

from .representation_labels import build_representation_labels


def _features(encounter: dict, patient: dict) -> dict:
    departure = datetime.fromisoformat(encounter["departure_at"])
    birth = date.fromisoformat(patient["birth_date"])
    age = (
        departure.year
        - birth.year
        - ((departure.month, departure.day) < (birth.month, birth.day))
    )
    return {
        "age": age,
        "chronic_condition_count": int(patient["chronic_condition_count"]),
        "hospital_id": encounter["hospital_id"],
        "arrival_mode": encounter["arrival_mode"],
        "triage_category": int(encounter["triage_category"]),
        "presentation_group": encounter["presentation_group"],
        "waiting_time_minutes": float(encounter["waiting_time_minutes"]),
        "ed_length_of_stay_minutes": float(
            encounter["ed_length_of_stay_minutes"]
        ),
    }


def _scores(actual: list[int], probabilities) -> dict:
    return {
        "brier_score": round(
            float(brier_score_loss(actual, probabilities)), 4
        ),
        "roc_auc": round(
            float(roc_auc_score(actual, probabilities)), 4
        ),
        "average_precision": round(
            float(average_precision_score(actual, probabilities)), 4
        ),
    }


def evaluate_representation_model(
    encounters: list[dict],
    patients: list[dict],
    manifest: dict,
) -> dict:
    encounters = list(encounters)
    patients = list(patients)

    if int(manifest["generator_version"]) != 2:
        raise ValueError("re-presentation evaluation requires generator v2")

    encounter_by_id = {
        row["encounter_id"]: row for row in encounters
    }
    patient_by_id = {
        row["patient_id"]: row for row in patients
    }
    if len(encounter_by_id) != len(encounters):
        raise ValueError("duplicate encounter ID")
    if len(patient_by_id) != len(patients):
        raise ValueError("duplicate patient ID")

    start = datetime.fromisoformat(manifest["start_at"])
    hours = int(manifest["hours"])
    split_at = start + timedelta(hours=hours / 2)
    labels = build_representation_labels(
        encounters, manifest["start_at"], hours
    )

    train = []
    test = []
    purged_pre_split = 0

    for label in labels:
        if label["followup_status"] != "eligible":
            continue

        encounter = encounter_by_id[label["encounter_id"]]
        if encounter["patient_id"] != label["patient_id"]:
            raise ValueError("label and encounter disagree on patient")
        patient = patient_by_id[label["patient_id"]]

        departure = datetime.fromisoformat(label["departure_at"])
        label_available = datetime.fromisoformat(
            label["label_available_at"]
        )
        record = (
            _features(encounter, patient),
            int(label["seven_day_return"]),
            departure,
            label_available,
        )

        if departure < split_at:
            if label_available <= split_at:
                train.append(record)
            else:
                purged_pre_split += 1
        else:
            test.append(record)

    if not train or not test:
        raise ValueError(
            "need a longer run with eligible training and test visits"
        )

    train_actual = [record[1] for record in train]
    test_actual = [record[1] for record in test]
    if set(train_actual) != {0, 1} or set(test_actual) != {0, 1}:
        raise ValueError("training and test sets both need return classes")

    baseline_probability = sum(train_actual) / len(train_actual)
    baseline_probabilities = [
        baseline_probability
    ] * len(test_actual)

    model = Pipeline([
        ("vectorizer", DictVectorizer(sparse=False)),
        (
            "classifier",
            HistGradientBoostingClassifier(
                max_iter=150,
                max_leaf_nodes=15,
                min_samples_leaf=20,
                l2_regularization=1.0,
                early_stopping=False,
                random_state=42,
            ),
        ),
    ])
    model.fit(
        [record[0] for record in train],
        train_actual,
    )
    model_probabilities = model.predict_proba(
        [record[0] for record in test]
    )[:, 1]

    return {
        "return_selection": manifest.get(
            "return_selection", "uniform"
        ),
        "split_at_utc": split_at.isoformat(),
        "training_rows": len(train),
        "purged_pre_split_rows": purged_pre_split,
        "test_rows": len(test),
        "latest_training_label_at_utc": max(
            record[3] for record in train
        ).isoformat(),
        "earliest_test_departure_at_utc": min(
            record[2] for record in test
        ).isoformat(),
        "training_return_rate": round(
            baseline_probability, 4
        ),
        "test_return_rate": round(
            sum(test_actual) / len(test_actual), 4
        ),
        "encoded_feature_count": len(
            model.named_steps["vectorizer"].get_feature_names_out()
        ),
        "baseline": _scores(
            test_actual, baseline_probabilities
        ),
        "model": _scores(
            test_actual, model_probabilities
        ),
    }


def evaluate_run(run: Path) -> dict:
    manifest = json.loads(
        (run / "manifest.json").read_text(encoding="utf-8")
    )

    def read_csv(filename: str) -> list[dict]:
        with (run / filename).open(
            newline="", encoding="utf-8"
        ) as handle:
            return list(csv.DictReader(handle))

    return evaluate_representation_model(
        read_csv("encounters.csv"),
        read_csv("patients.csv"),
        manifest,
    )


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate seven-day ED re-presentation prediction"
    )
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(evaluate_run(args.run), indent=2))


if __name__ == "__main__":
    main()