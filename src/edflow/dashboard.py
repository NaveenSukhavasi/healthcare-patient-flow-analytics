import argparse
import csv
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Synthetic ED patient flow</title>
  <style>
    body { font: 16px system-ui, sans-serif; margin: 0; color: #172638;
           background: #f3f6f9; }
    header { background: #123454; color: white; padding: 28px max(24px, 5vw); }
    h1 { margin: 0 0 8px; font-size: 1.8rem; }
    header p { margin: 0; color: #d4e4ef; }
    main { max-width: 1100px; margin: 28px auto; padding: 0 20px; }
    .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
             gap: 14px; margin-bottom: 26px; }
    .card, .panel { background: white; border: 1px solid #dce5ec;
                    border-radius: 12px; padding: 18px; }
    .card strong { display: block; font-size: 1.6rem; margin-top: 6px; }
    .label { color: #536779; }
    .panel { margin-bottom: 22px; overflow-x: auto; }
    h2 { margin: 0 0 14px; font-size: 1.2rem; }
    table { width: 100%; border-collapse: collapse; min-width: 680px; }
    th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #e5ebf0; }
    th { color: #40566b; background: #f7f9fb; }
    select { font: inherit; padding: 8px; margin-bottom: 14px; }
    footer { max-width: 1100px; margin: 20px auto 36px; padding: 0 20px;
             color: #536779; }
  </style>
</head>
<body>
  <header>
    <h1>Synthetic ED patient flow</h1>
    <p>Local dashboard for fictional hospitals and generated data</p>
  </header>
  <main>
    <div class="cards" id="summary"></div>
    <section class="panel">
      <h2>Hospital KPIs</h2>
      <table>
        <thead><tr>
          <th>Hospital</th><th>Presentations</th><th>Median wait (min)</th>
          <th>Median stay (min)</th><th>Four-hour completion</th>
          <th>Admission rate</th>
        </tr></thead>
        <tbody id="hospitals"></tbody>
      </table>
    </section>
    <section class="panel">
      <h2>Daily KPIs</h2>
      <label for="hospital-filter">Hospital: </label>
      <select id="hospital-filter"><option value="">All hospitals</option></select>
      <table>
        <thead><tr>
          <th>Date (UTC)</th><th>Hospital</th><th>Presentations</th>
          <th>Median wait (min)</th><th>Four-hour completion</th>
        </tr></thead>
        <tbody id="daily"></tbody>
      </table>
    </section>
  </main>
  <footer>Fully synthetic portfolio data. Not a clinical tool.</footer>
  <script>
    function cell(row, value) {
      const td = document.createElement("td");
      td.textContent = value ?? "";
      row.appendChild(td);
    }
    function fillTable(id, records, fields) {
      const body = document.getElementById(id);
      body.replaceChildren();
      for (const record of records) {
        const tr = document.createElement("tr");
        for (const field of fields) cell(tr, record[field]);
        body.appendChild(tr);
      }
    }
    function card(label, value) {
      const box = document.createElement("div");
      box.className = "card";
      const caption = document.createElement("span");
      caption.className = "label";
      caption.textContent = label;
      const number = document.createElement("strong");
      number.textContent = value;
      box.append(caption, number);
      document.getElementById("summary").appendChild(box);
    }
    async function getJson(path) {
      const response = await fetch(path);
      if (!response.ok) throw new Error(`Request failed: ${path}`);
      return response.json();
    }
    async function loadDaily() {
      const selected = document.getElementById("hospital-filter").value;
      const query = selected ? `?hospital_id=${encodeURIComponent(selected)}` : "";
      const rows = await getJson(`/api/daily${query}`);
      fillTable("daily", rows, [
        "arrival_date_utc", "hospital_id", "presentation_count",
        "median_waiting_time_minutes", "four_hour_completion_rate"
      ]);
    }
    async function start() {
      const [manifest, hospitals] = await Promise.all([
        getJson("/api/manifest"), getJson("/api/hospitals")
      ]);
      card("Patients", manifest.patient_count);
      card("Encounters", manifest.encounter_count);
      card("Hospitals", manifest.hospital_count);
      card("Run hours", manifest.hours);
      fillTable("hospitals", hospitals, [
        "hospital_id", "presentation_count", "median_waiting_time_minutes",
        "median_ed_length_of_stay_minutes", "four_hour_completion_rate",
        "admission_rate"
      ]);
      const filter = document.getElementById("hospital-filter");
      for (const hospital of hospitals) {
        const option = document.createElement("option");
        option.value = hospital.hospital_id;
        option.textContent = hospital.hospital_id;
        filter.appendChild(option);
      }
      filter.addEventListener("change", loadDaily);
      await loadDaily();
    }
    start().catch(error => {
      document.querySelector("main").textContent = error.message;
    });
  </script>
</body>
</html>
"""


def load_run(run):
    run = Path(run)
    with (run / "manifest.json").open(encoding="utf-8") as handle:
        manifest = json.load(handle)

    def read_csv(filename):
        with (run / filename).open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    hospitals = read_csv("hospital_kpis.csv")
    daily = read_csv("hospital_daily_kpis.csv")
    if (
        len(hospitals) != manifest["hospital_kpi_count"]
        or len(daily) != manifest["daily_kpi_count"]
    ):
        raise ValueError("KPI files do not match the manifest")

    return {"manifest": manifest, "hospitals": hospitals, "daily": daily}


def make_handler(data):
    hospital_ids = {row["hospital_id"] for row in data["hospitals"]}

    class Handler(BaseHTTPRequestHandler):
        def send_body(self, payload, content_type, status=200):
            body = payload.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, value, status=200):
            self.send_body(json.dumps(value), "application/json", status)

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == "/":
                self.send_body(PAGE, "text/html")
            elif url.path == "/health":
                self.send_json({"status": "ok"})
            elif url.path == "/api/manifest":
                self.send_json(data["manifest"])
            elif url.path == "/api/hospitals":
                self.send_json(data["hospitals"])
            elif url.path == "/api/daily":
                selected = parse_qs(url.query).get("hospital_id", [""])[0]
                if selected and selected not in hospital_ids:
                    self.send_json({"error": "unknown hospital_id"}, 400)
                    return
                rows = [
                    row for row in data["daily"]
                    if not selected or row["hospital_id"] == selected
                ]
                self.send_json(rows)
            else:
                self.send_json({"error": "not found"}, 404)

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser(description="Serve synthetic ED KPIs locally")
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    data = load_run(args.run)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(data))
    print(f"Open http://127.0.0.1:{server.server_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()