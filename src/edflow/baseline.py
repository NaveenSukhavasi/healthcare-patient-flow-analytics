import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean, median


def _utc(value: str) -> datetime:
    result = datetime.fromisoformat(value)
    if result.utcoffset() != timedelta(0):
        raise ValueError("timestamps must be UTC")
    return result


def evaluate_waiting_time_baselines(training_rows, encounters) -> dict:
    encounter_by_id = {}
    for encounter in encounters:
        encounter_id = encounter["encounter_id"]
        if encounter_id in encounter_by_id:
            raise ValueError("duplicate encounter_id")
        encounter_by_id[encounter_id] = encounter

    records = []
    seen_ids = set()
    for row in training_rows:
        encounter_id = row["encounter_id"]
        if encounter_id in seen_ids or encounter_id not in encounter_by_id:
            raise ValueError("duplicate or unknown training encounter")
        seen_ids.add(encounter_id)

        encounter = encounter_by_id[encounter_id]
        arrival = _utc(row["arrival_at"])
        started = _utc(encounter["treatment_start_at"])
        waiting = float(row["waiting_time_minutes"])

        if (
            arrival != _utc(encounter["arrival_at"])
            or row["hospital_id"] != encounter["hospital_id"]
            or started < arrival
            or waiting < 0
            or abs(waiting - (started - arrival).total_seconds() / 60) > 0.011
        ):
            raise ValueError("inconsistent waiting-time record")

        records.append((arrival, row["hospital_id"], waiting, started))

    arrival_times = sorted({record[0] for record in records})
    if len(arrival_times) < 2:
        raise ValueError("need at least two distinct arrival times")

    split_at = arrival_times[int(len(arrival_times) * 0.8)]
    train = [
        record for record in records
        if record[0] < split_at and record[3] < split_at
    ]
    test = [record for record in records if record[0] >= split_at]
    excluded = sum(
        record[0] < split_at and record[3] >= split_at
        for record in records
    )
    if not train or not test:
        raise ValueError("chronological split has no eligible train or test rows")

    global_median = float(median(record[2] for record in train))
    waits_by_hospital = defaultdict(list)
    for _, hospital_id, waiting, _ in train:
        waits_by_hospital[hospital_id].append(waiting)
    hospital_medians = {
        hospital_id: float(median(waits))
        for hospital_id, waits in waits_by_hospital.items()
    }

    return {
        "split_at_utc": split_at.isoformat(),
        "training_rows": len(train),
        "excluded_unavailable_labels": excluded,
        "test_rows": len(test),
        "global_median_minutes": round(global_median, 2),
        "global_median_mae_minutes": round(
            mean(abs(waiting - global_median) for _, _, waiting, _ in test), 2
        ),
        "hospital_median_mae_minutes": round(
            mean(
                abs(waiting - hospital_medians.get(hospital_id, global_median))
                for _, hospital_id, waiting, _ in test
            ),
            2,
        ),
    }


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate chronological waiting-time baselines"
    )
    parser.add_argument("--run", required=True, type=Path)
    args = parser.parse_args(argv)

    def read_csv(filename):
        with (args.run / filename).open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    report = evaluate_waiting_time_baselines(
        read_csv("arrival_training.csv"),
        read_csv("encounters.csv"),
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()