# Intelligent Emergency Department Patient Flow Platform

A software engineering and data science portfolio project built around fully
synthetic emergency department activity at fictional Victorian-style hospitals.

## Current status

The local generator produces linked patient, arrival, triage, treatment-start,
and departure records across eight fictional hospitals. Treatment uses finite
ED capacity. Each run writes `patients.csv`, `events.jsonl`, `encounters.csv`,
`arrival_snapshots.csv`, `arrival_training.csv`, `hospital_kpis.csv`,
`hospital_daily_kpis.csv`, and `manifest.json`.

Arrival snapshots use only events strictly earlier than each arrival.
The offline training table joins completed outcomes to arrival-known features.
Its target columns are labels, not predictors.

## Waiting-time reference baseline

`python -m edflow.baseline --run <run-directory>` evaluates global and
per-hospital median waiting times on a chronological holdout. A training
label is used only if treatment started before the test period begins.

A 14-day synthetic run (`--hours 336 --patients 1000 --seed 42`) had
2,270 eligible training rows and 568 test rows. Both baselines achieved
29.09 minutes mean absolute error. This is a reference score for later
models, not a clinical performance claim.

## Planned capabilities

- Feature-based waiting-time, admission, breach-risk, and re-presentation models
- Broader historical analytics and model validation
- Tested API and a usable web interface
- Local event streaming and selective, cost-conscious cloud deployment

This is a synthetic portfolio system, not a clinically validated tool or
medical advice.