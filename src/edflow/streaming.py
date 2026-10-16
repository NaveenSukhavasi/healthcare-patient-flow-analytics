import argparse
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from .events import EDEvent, EventType


FIELDS = {
    "event_id",
    "encounter_id",
    "patient_id",
    "hospital_id",
    "occurred_at",
    "event_type",
    "payload",
    "schema_version",
}


def validate_record(record: dict) -> dict:
    """Validate a Kafka message against the existing ED event contract."""
    if not isinstance(record, dict) or set(record) != FIELDS:
        raise ValueError("invalid event fields")

    event = EDEvent(
        event_id=record["event_id"],
        encounter_id=record["encounter_id"],
        patient_id=record["patient_id"],
        hospital_id=record["hospital_id"],
        occurred_at=datetime.fromisoformat(record["occurred_at"]),
        event_type=EventType(record["event_type"]),
        payload=record["payload"],
        schema_version=record["schema_version"],
    )
    return event.to_record()


def initialise_store(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS ed_events (
            event_id TEXT PRIMARY KEY,
            encounter_id TEXT NOT NULL,
            patient_id TEXT NOT NULL,
            hospital_id TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            record_json TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS ed_events_time
        ON ed_events(occurred_at, event_id)
    """)
    connection.commit()


def store_record(connection: sqlite3.Connection, record: dict) -> bool:
    """Store once by event ID; reject a conflicting replay."""
    valid = validate_record(record)
    encoded = json.dumps(valid, sort_keys=True, separators=(",", ":"))

    previous = connection.execute(
        "SELECT record_json FROM ed_events WHERE event_id = ?",
        (valid["event_id"],),
    ).fetchone()
    if previous is not None:
        if previous[0] != encoded:
            raise ValueError("conflicting record for event ID")
        return False

    connection.execute(
        """
        INSERT INTO ed_events (
            event_id, encounter_id, patient_id, hospital_id,
            occurred_at, event_type, record_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            valid["event_id"],
            valid["encounter_id"],
            valid["patient_id"],
            valid["hospital_id"],
            valid["occurred_at"],
            valid["event_type"],
            encoded,
        ),
    )
    connection.commit()
    return True


def ensure_topic(bootstrap: str, topic: str) -> None:
    from confluent_kafka import KafkaError, KafkaException
    from confluent_kafka.admin import AdminClient, NewTopic

    admin = AdminClient({"bootstrap.servers": bootstrap})
    for _ in range(30):
        try:
            admin.list_topics(timeout=2)
            break
        except KafkaException:
            time.sleep(1)
    else:
        raise RuntimeError("Kafka broker did not become ready")

    future = admin.create_topics([
        NewTopic(topic, num_partitions=1, replication_factor=1)
    ])[topic]
    try:
        future.result(timeout=30)
    except KafkaException as exc:
        if exc.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:
            raise


def replay_events(
    events_file: Path,
    bootstrap: str,
    topic: str,
    limit: int | None,
    delay_ms: int,
) -> int:
    from confluent_kafka import Producer

    ensure_topic(bootstrap, topic)
    producer = Producer({
        "bootstrap.servers": bootstrap,
        "acks": "all",
    })
    delivery_errors = []

    def delivered(error, _message):
        if error is not None:
            delivery_errors.append(str(error))

    sent = 0
    with events_file.open(encoding="utf-8") as handle:
        for line in handle:
            if limit is not None and sent >= limit:
                break
            if not line.strip():
                continue

            record = validate_record(json.loads(line))
            producer.produce(
                topic,
                key=record["encounter_id"].encode("utf-8"),
                value=json.dumps(record, sort_keys=True).encode("utf-8"),
                callback=delivered,
            )
            producer.poll(0)
            sent += 1
            if delay_ms:
                time.sleep(delay_ms / 1000)

    remaining = producer.flush(60)
    if remaining or delivery_errors:
        raise RuntimeError(
            f"Kafka delivery failed: {remaining} pending; "
            f"errors={delivery_errors[:3]}"
        )
    return sent


def consume_to_sqlite(
    database: Path,
    bootstrap: str,
    topic: str,
    expected: int,
) -> dict:
    from confluent_kafka import Consumer, KafkaException

    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database)
    initialise_store(connection)

    consumer = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": f"edflow-demo-{uuid4().hex}",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    consumer.subscribe([topic])

    received = 0
    inserted = 0
    idle_deadline = time.monotonic() + 30

    try:
        while received < expected:
            message = consumer.poll(1)
            if message is None:
                if time.monotonic() >= idle_deadline:
                    raise TimeoutError(
                        f"received {received} of {expected} events"
                    )
                continue
            if message.error():
                raise KafkaException(message.error())

            record = json.loads(message.value().decode("utf-8"))
            inserted += int(store_record(connection, record))
            consumer.commit(message=message, asynchronous=False)
            received += 1
            idle_deadline = time.monotonic() + 30

        stored_total = connection.execute(
            "SELECT COUNT(*) FROM ed_events"
        ).fetchone()[0]
        return {
            "received": received,
            "inserted": inserted,
            "stored_total": stored_total,
            "database": str(database),
        }
    finally:
        consumer.close()
        connection.close()


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Replay and consume synthetic ED events through Kafka"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    replay = commands.add_parser("replay")
    replay.add_argument("--run", required=True, type=Path)
    replay.add_argument("--topic", required=True)
    replay.add_argument("--bootstrap", default="localhost:9092")
    replay.add_argument("--limit", type=int)
    replay.add_argument("--delay-ms", type=int, default=0)

    consume = commands.add_parser("consume")
    consume.add_argument("--topic", required=True)
    consume.add_argument("--database", required=True, type=Path)
    consume.add_argument("--expected", required=True, type=int)
    consume.add_argument("--bootstrap", default="localhost:9092")

    args = parser.parse_args(argv)
    if args.command == "replay":
        if args.limit is not None and args.limit < 1:
            parser.error("--limit must be positive")
        if args.delay_ms < 0:
            parser.error("--delay-ms cannot be negative")
        sent = replay_events(
            args.run / "events.jsonl",
            args.bootstrap,
            args.topic,
            args.limit,
            args.delay_ms,
        )
        print(json.dumps({"sent": sent, "topic": args.topic}, indent=2))
    else:
        if args.expected < 1:
            parser.error("--expected must be positive")
        result = consume_to_sqlite(
            args.database,
            args.bootstrap,
            args.topic,
            args.expected,
        )
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()