# Intelligent Emergency Department Patient Flow Platform

A software engineering and data science portfolio project built around fully
synthetic emergency department activity at fictional Victorian-style hospitals.

## Current status

The local synthetic generator now produces linked patient records, arrival,
triage, treatment-start, and departure events across eight fictional hospitals.
Treatment uses finite ED capacity. Each run writes `patients.csv`, `hospital_kpis.csv`,  `hospital_daily_kpis.csv` , `events.jsonl`, `encounters.csv`, `arrival_snapshots.csv`, and `manifest.json`.
Arrival snapshots use only events strictly earlier than each arrival.
Prediction models, API, streaming, web interface, and cloud deployment remain
planned.

## Planned capabilities

- Reproducible patient-flow simulation and historical analytics
- Arrival-time operational features with checks against data leakage
- Waiting-time, admission, breach-risk, and re-presentation modelling
- Tested API and a usable web interface
- Local event streaming and selective, cost-conscious cloud deployment

This is a synthetic portfolio system, not a clinically validated tool or
medical advice.