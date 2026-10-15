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

Offline experiments now cover arrival-time waiting prediction, arrival-time
admission prediction, post-triage admission prediction, and arrival-time
four-hour breach prediction. These are evaluations on synthetic data, not
deployed clinical models.

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

## Admission prediction experiments

At arrival, an admission classifier was compared with a baseline that predicts
the training-set admission rate. Both were evaluated on a chronological
holdout. Encounters whose departure outcome was unavailable at the split were
excluded from training.

| Seed | Eligible train | Test | Prevalence Brier | Arrival model Brier |
| --- | ---: | ---: | ---: | ---: |
| 42 | 2,249 | 568 | 0.2429 | 0.2555 |
| 73 | 2,237 | 570 | 0.2366 | 0.2470 |

Lower Brier scores are better. The arrival-time model did not beat the
prevalence baseline on either of these synthetic runs. Triage category is
unavailable at arrival, so it is not used by that model.

A separate post-triage experiment compares the prevalence baseline, an
admission-rate baseline for each triage category, and a regularized logistic
regression using arrival-known features plus triage category. All three use
the same chronological holdout. Training uses only admission outcomes known
before the holdout begins.

| Seed | Eligible train | Test | Prevalence Brier | Category Brier | Logistic Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| 42 | 2,249 | 568 | 0.2429 | 0.2041 | 0.2044 |
| 73 | 2,237 | 570 | 0.2366 | 0.1749 | 0.1800 |
| 13 | 2,224 | 566 | ~0.24 | ~0.19 | ~0.18 |
| 101 | 2,274 | 578 | ~0.23 | ~0.19 | ~0.18 |
| 202 | 2,268 | 575 | ~0.24 | ~0.19 | ~0.19 |

All five runs used `--hours 336 --patients 1000`. Values marked `~` were
copied from a PowerShell table that displayed two decimal places. The
category baseline narrowly beats logistic regression on seeds 42 and 73;
logistic regression appears better at the displayed precision on seeds 13
and 101. The rounded seed 202 scores do not establish which is better.
Both post-triage approaches improve on prevalence in these synthetic runs.
More validation is needed before selecting a preferred model.

## Four-hour breach prediction experiment

A four-hour breach means the encounter's arrival-to-departure time exceeds
240 minutes. The arrival-time baseline predicts the breach rate among
eligible training encounters. A histogram gradient boosting classifier uses
only arrival-known features. Both are scored on the same chronological
holdout using Brier score. A training encounter is eligible only if its
departure outcome was known before the holdout begins.

| Seed | Eligible train | Test | Test breach rate | Baseline Brier | Model Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| 42 | 2,249 | 568 | 0.4613 | 0.2534 | 0.2170 |
| 73 | 2,237 | 570 | 0.4070 | 0.2414 | 0.2382 |
| 13 | 2,224 | 566 | 0.4470 | 0.2484 | 0.2198 |
| 101 | 2,274 | 578 | 0.4308 | 0.2467 | 0.2270 |
| 202 | 2,268 | 575 | 0.3843 | 0.2381 | 0.2425 |

All five runs used `--hours 336 --patients 1000`. The model beats the
prevalence baseline on four runs, but is worse on seed 202. The gain on
seed 73 is small. These repeated synthetic runs come from the same
simulator; they do not establish performance on real hospital data.

## Planned capabilities

- Re-presentation model experiments
- Broader historical analytics and model validation
- Tested API and a usable web interface
- Local event streaming and selective, cost-conscious cloud deployment

This is a synthetic portfolio system, not a clinically validated tool or
medical advice.