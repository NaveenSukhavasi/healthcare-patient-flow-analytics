import argparse
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path


def _utc(value):
    result = datetime.fromisoformat(value)
    if result.utcoffset() != timedelta(0):
        raise ValueError("timestamps must be UTC")
    return result


def evaluate_admission_baseline(training_rows, encounters):
    training_rows = list(training_rows)
    encounters = list(encounters)
    encounter_by_id = {row["encounter_id"]: row for row in encounters}
    if len(encounter_by_id) != len(encounters):
        raise ValueError("duplicate encounter_id")

    records = []
    seen = set()
    for row in training_rows:
        encounter_id = row["encounter_id"]
        if encounter_id in seen or encounter_id not in encounter_by_id:
            raise ValueError("duplicate or unknown training encounter")
        seen.add(encounter_id)

        encounter = encounter_by_id[encounter_id]
        arrival = _utc(row["arrival_at"])
        departure = _utc(encounter["departure_at"])
        admitted = int(row["admitted_flag"])
        if (
            arrival != _utc(encounter["arrival_at"])
            or row["hospital_id"] != encounter["hospital_id"]
            or departure < arrival
            or admitted not in (0, 1)
            or admitted != int(encounter["admitted_flag"])
        ):
            raise ValueError("inconsistent admission record")
        records.append((arrival, departure, admitted))

    arrival_times = sorted({arrival for arrival, _, _ in records})
    if len(arrival_times) < 2:
        raise ValueError("need at least two distinct arrival times")

    split_at = arrival_times[int(len(arrival_times) * 0.8)]
    train = [
        admitted for arrival, departure, admitted in records
        if arrival < split_at and departure < split_at
    ]
    test = [
        admitted for arrival, _, admitted in records
        if arrival >= split_at
    ]
    excluded = sum(
        arrival < split_at and departure >= split_at
        for arrival, departure, _ in records
    )
    if not train or not test:
        raise ValueError("chronological split has no eligible train or test rows")

    probability = sum(train) / len(train)
    return {
        "split_at_utc": split_at.isoformat(),
        "training_rows": len(train),
        "excluded_unavailable_labels": excluded,
        "test_rows": len(test),
        "training_admission_rate": round(probability, 4),
        "test_admission_rate": round(sum(test) / len(test), 4),
        "baseline_brier_score": round(
            sum((admitted - probability) ** 2 for admitted in test) / len(test),
            4,
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Evaluate a chronological admission probability baseline"
    )
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args(argv)

    def read_csv(filename):
        with (args.run / filename).open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    report = evaluate_admission_baseline(
        read_csv("arrival_training.csv"),
        read_csv("encounters.csv"),
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()