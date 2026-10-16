# Synthetic Emergency Department Patient Flow

[Open the public dashboard](https://naveensukhavasi.github.io/healthcare-patient-flow-analytics/)

A portfolio project that simulates patient flow across eight fictional emergency departments. It generates timestamped events, encounter and KPI tables, evaluates prediction models, and offers a local streaming and API demo. All records are synthetic. This is not a clinical tool or medical advice.

## What works

| Component | Implementation |
| --- | --- |
| Simulator | Reproducible Python generator with capacity-limited treatment and version-two, overlap-safe patient assignment |
| Data checks | Event and encounter tests plus seven-day follow-up, censoring, and overlap audits |
| Models | Chronological evaluations for waiting time, admission, four-hour breach, and seven-day re-presentation |
| Local streaming | Apache Kafka in Docker Compose; replay producer and SQLite consumer |
| Local app | FastAPI endpoints and a React dashboard with generated or streamed events |
| Public demo | GitHub Pages dashboard built from a generated, read-only JSON snapshot |
| Verification | Python tests, web build, and container build in GitHub Actions |

The public page is a **snapshot**, generated during the Pages workflow. It does not run FastAPI or Kafka in the cloud. Those components work locally. The public deployment uses GitHub Pages and does not require a Google Cloud billing account.

## Run the local app

From the repository folder in PowerShell, with the project's Python virtual environment and Node dependencies installed:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
$run = "data/generated/demo-$(Get-Date -Format yyyyMMdd-HHmmss)"
.\.venv\Scripts\python.exe -m edflow --output $run --start 2025-01-01T00:00:00+00:00 --hours 336 --patients 40000 --seed 42 --generator-version 2 --return-probability 0.1 --return-risk-weighting
$env:EDFLOW_RUN = (Resolve-Path $run).Path
.\.venv\Scripts\python.exe -m uvicorn edflow.api:create_app --factory --host 127.0.0.1 --port 8000
```

In a second terminal, run `npm --prefix apps/web run dev`, then open the URL printed by Vite. The development server proxies `/api` to FastAPI. `GET /health` checks the API; `/api/manifest`, `/api/hospitals`, `/api/daily`, `/api/representation`, and `/api/events` provide dashboard data. Stop each server with Ctrl+C.

Each run writes `patients.csv`, `events.jsonl`, `encounters.csv`, `arrival_snapshots.csv`, `arrival_training.csv`, `hospital_kpis.csv`, `hospital_daily_kpis.csv`, and `manifest.json`. The output directory must be new for each run. Version 1 is still the CLI default to reproduce earlier experiments; select version 2 for valid patient visit assignment and re-presentation work.

## Reproduce the re-presentation evaluation

The following 28-day version-two run uses a synthetic chronic-condition-weighted return selection. It is separate from the 14-day public dashboard run.

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
$modelRun = "data/generated/model-28d-$(Get-Date -Format yyyyMMdd-HHmmss)"
.\.venv\Scripts\python.exe -m edflow --output $modelRun --start 2025-01-01T00:00:00+00:00 --hours 672 --patients 40000 --seed 42 --generator-version 2 --return-probability 0.1 --return-risk-weighting
.\.venv\Scripts\python.exe -m edflow.representation_audit --run $modelRun
.\.venv\Scripts\python.exe -m edflow.representation_model --run $modelRun
```

For this configuration, the generator produced 5,762 encounters and 23,048 events. The chronological model evaluation trained on 855 eligible visits, purged 872 pre-split visits whose labels were not yet known, and tested on 936 visits. Its ROC AUC was 0.6072 and average precision 0.2068 versus a prevalence baseline of 0.1549. Its Brier score was **0.1717, worse than the baseline's 0.1416**. The model shows some ranking signal in this synthetic run but is not a better calibrated risk predictor. The exact report is in [docs/representation_model_result.json](docs/representation_model_result.json).

Labels use only discharged index visits with a complete seven-day follow-up window. Admitted ED departures are excluded because this simulator has no inpatient discharge time; incomplete follow-ups are censored. Training uses only labels available before the chronological split. See [data contract](docs/data_contract.md) and [re-presentation design](docs/representation_design.md).

## Local Kafka demo

Install `requirements-stream.txt` into the virtual environment, then start Kafka with `docker compose up -d kafka`. Run the consumer in one terminal:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
.\.venv\Scripts\python.exe -m edflow.streaming consume --topic edflow-events --database data/generated/stream-demo.sqlite --expected 100
```

Replay a generated run in another terminal:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
.\.venv\Scripts\python.exe -m edflow.streaming replay --run 'data/generated/your-run-name' --topic edflow-events --limit 100
```

Replace `your-run-name` with the generated directory printed by the simulator. Set `EDFLOW_STREAM_DB` to the SQLite file before starting FastAPI to show consumed events in `/api/events`; otherwise the API shows recent events from the generated run. Kafka binds to local port 9092 in `compose.yaml`.

## Other model findings

The earlier waiting-time, admission, and four-hour breach experiments used version-one data and chronological holdouts. They are not evidence of performance on version-two data or real patients. For seed 42, the waiting-time model reduced mean absolute error from 29.09 to 23.80 minutes; the arrival-time admission model had a worse Brier score than its prevalence baseline (0.2555 versus 0.2429); and the breach model improved Brier score from 0.2534 to 0.2170. Results varied across seeds, including a breach run where the model was worse than baseline. See the code and tests for evaluation details.

## Public deployment and verification

The [Pages workflow](.github/workflows/pages.yml) generates a deterministic version-two run, exports only dashboard JSON, builds React in static mode, and publishes `apps/web/dist` whenever `main` is pushed. The public snapshot contains no patient-level demographics. The [CI workflow](.github/workflows/ci.yml) runs Python tests, builds the web app, and builds the container. The latest local verification before deployment passed 62 Python tests and the React production build.

This project is a software and data-science demonstration. Its hospital settings, return process, and model results are illustrative, not calibrated to real healthcare data. The static site is suitable for a no-billing portfolio demo; it is not a hosted streaming service.
