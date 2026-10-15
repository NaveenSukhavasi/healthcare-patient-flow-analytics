import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from .admission_baseline import _utc, evaluate_admission_baseline


def evaluate_triage_admission_baseline(training_rows, encounters):
    training_rows = list(training_rows)
    encounters = list(encounters)
    report = evaluate_admission_baseline(training_rows, encounters)
    split_at = _utc(report["split_at_utc"])
    encounter_by_id = {row["encounter_id"]: row for row in encounters}

    labels_by_category = defaultdict(list)
    heldout = []

    for row in training_rows:
        encounter = encounter_by_id[row["encounter_id"]]
        arrival = _utc(row["arrival_at"])
        triage = _utc(encounter["triage_at"])
        departure = _utc(encounter["departure_at"])
        category = int(encounter["triage_category"])
        admitted = int(row["admitted_flag"])

        if not arrival <= triage <= departure or category not in range(1, 6):
            raise ValueError("invalid triage record")

        if arrival < split_at:
            if departure < split_at:
                labels_by_category[category].append(admitted)
        else:
            heldout.append((category, admitted))

    if (
        sum(len(labels) for labels in labels_by_category.values())
        != report["training_rows"]
        or len(heldout) != report["test_rows"]
    ):
        raise ValueError("triage split differs from admission baseline")

    global_rate = (
        sum(sum(labels) for labels in labels_by_category.values())
        / report["training_rows"]
    )
    category_rates = {
        category: sum(labels) / len(labels)
        for category, labels in labels_by_category.items()
    }
    score = sum(
        (admitted - category_rates.get(category, global_rate)) ** 2
        for category, admitted in heldout
    ) / len(heldout)

    return {
        **report,
        "prediction_point": "after_triage",
        "category_training_counts": {
            str(category): len(labels)
            for category, labels in sorted(labels_by_category.items())
        },
        "category_brier_score": round(score, 4),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Evaluate a post-triage admission category baseline"
    )
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args(argv)

    def read_csv(filename):
        with (args.run / filename).open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    report = evaluate_triage_admission_baseline(
        read_csv("arrival_training.csv"),
        read_csv("encounters.csv"),
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()