import json
from http.server import ThreadingHTTPServer
from threading import Thread
from urllib.request import urlopen

from edflow.__main__ import main
from edflow.dashboard import load_run, make_handler


def test_dashboard_serves_generated_kpis(tmp_path):
    run = tmp_path / "run"
    main([
        "--output", str(run),
        "--hours", "3",
        "--patients", "20",
        "--seed", "7",
    ])
    data = load_run(run)

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(data))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    try:
        with urlopen(f"{base}/health", timeout=5) as response:
            assert json.load(response)["status"] == "ok"

        with urlopen(f"{base}/api/manifest", timeout=5) as response:
            manifest = json.load(response)
            assert manifest["encounter_count"] > 0

        with urlopen(f"{base}/api/hospitals", timeout=5) as response:
            hospitals = json.load(response)
            assert len(hospitals) == manifest["hospital_kpi_count"]
            assert hospitals

        hospital_id = hospitals[0]["hospital_id"]
        with urlopen(
            f"{base}/api/daily?hospital_id={hospital_id}", timeout=5
        ) as response:
            assert all(
                row["hospital_id"] == hospital_id
                for row in json.load(response)
            )

        with urlopen(base, timeout=5) as response:
            assert b"Synthetic ED patient flow" in response.read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)