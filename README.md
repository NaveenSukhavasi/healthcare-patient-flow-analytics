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

## Waiting-time baseline and model

`python -m edflow.baseline --run <run-directory>` evaluates global and
per-hospital median waiting times on a chronological holdout. A training
label is used only if treatment started before the test period begins.

The feature-based model uses only the arrival-time feature allowlist. Its
encoder and regressor are fitted on eligible training rows, then evaluated
on the same chronological holdout as the median baselines.

| Seed | Eligible train | Test | Global median MAE | Model MAE |
| --- | ---: | ---: | ---: | ---: |
| 42 | 2,270 | 568 | 29.09 min | 23.80 min |
| 73 | 2,265 | 570 | 18.20 min | 15.41 min |

Both runs used `--hours 336 --patients 1000`. These are synthetic,
single-split results, not clinical performance claims.

Subgroup diagnostics by hospital and arrival mode are included in the model
report. The model improves overall MAE on both runs, but some hospital groups
are slightly worse than the global median. Seed 42's H03 group retains a high
62.97-minute MAE despite improving on its 79.67-minute baseline. These
synthetic subgroup results are exploratory.

## Admission prediction experiment

An arrival-time admission classifier was evaluated against the training-set
admission rate on the same chronological holdout. Encounters whose departure
outcome was unavailable at the split were excluded from training.

| Seed | Eligible train | Test | Prevalence baseline Brier | Model Brier |
| --- | ---: | ---: | ---: | ---: |
| 42 | 2,249 | 568 | 0.2429 | 0.2555 |
| 73 | 2,237 | 570 | 0.2366 | 0.2470 |

Lower Brier scores are better. The arrival-time model did not beat the
prevalence baseline on either synthetic run. Triage category, a strong
driver of admission in the simulator, is unavailable at arrival; a later
post-triage prediction is the next experiment.

## Planned capabilities

- Post-triage admission, breach-risk, and re-presentation model experiments
- Broader historical analytics and model validation
- Tested API and a usable web interface
- Local event streaming and selective, cost-conscious cloud deployment

This is a synthetic portfolio system, not a clinically validated tool or
medical advice.