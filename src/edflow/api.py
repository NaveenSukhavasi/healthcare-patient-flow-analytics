import csv
import json
import os
import sqlite3
from collections import deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from .dashboard import load_run
from .representation_audit import audit_representation


def create_app(
    run_dir: Path | None = None,
    stream_db: Path | None = None,
) -> FastAPI:
    if run_dir is None:
        configured = os.environ.get("EDFLOW_RUN")
        if not configured:
            raise RuntimeError("set EDFLOW_RUN to a generated run directory")
        run_dir = Path(configured)

    run_dir = Path(run_dir)
    if stream_db is None:
        configured_db = os.environ.get("EDFLOW_STREAM_DB")
        stream_db = Path(configured_db) if configured_db else None

    data = load_run(run_dir)
    manifest = data["manifest"]
    hospital_ids = {
        row["hospital_id"] for row in data["hospitals"]
    }

    if manifest.get("generator_version") == 2:
        with (run_dir / "encounters.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            encounters = list(csv.DictReader(handle))
        representation = {
            "available": True,
            **audit_representation(
                encounters,
                manifest["start_at"],
                int(manifest["hours"]),
            ),
        }
    else:
        representation = {
            "available": False,
            "reason": "Generate a version-two run for valid return statistics",
        }

    with (run_dir / "events.jsonl").open(
        encoding="utf-8"
    ) as handle:
        recent_file_events = list(deque(
            (json.loads(line) for line in handle if line.strip()),
            maxlen=100,
        ))

    app = FastAPI(
        title="Synthetic ED Patient Flow API",
        description="Portfolio demonstration using fictional data only.",
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/manifest")
    def get_manifest():
        return manifest

    @app.get("/api/hospitals")
    def get_hospitals():
        return data["hospitals"]

    @app.get("/api/daily")
    def get_daily(hospital_id: str = ""):
        if hospital_id and hospital_id not in hospital_ids:
            raise HTTPException(
                status_code=400,
                detail="unknown hospital_id",
            )
        return [
            row for row in data["daily"]
            if not hospital_id or row["hospital_id"] == hospital_id
        ]

    @app.get("/api/representation")
    def get_representation():
        return representation

    @app.get("/api/events")
    def get_events(limit: int = Query(20, ge=1, le=100)):
        if stream_db is not None and stream_db.exists():
            with sqlite3.connect(stream_db) as connection:
                rows = connection.execute(
                    """
                    SELECT record_json
                    FROM ed_events
                    ORDER BY occurred_at DESC, event_id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            return [json.loads(row[0]) for row in rows]

        return list(reversed(recent_file_events[-limit:]))

    web_dist = Path(__file__).resolve().parents[2] / "apps" / "web" / "dist"
    if web_dist.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=web_dist, html=True),
            name="web",
        )

    return app