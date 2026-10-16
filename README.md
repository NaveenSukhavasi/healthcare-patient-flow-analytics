# Intelligent Emergency Department Patient Flow Platform

A software engineering and data science portfolio project built around fully
synthetic emergency department (ED) activity at eight fictional
Victorian-style hospitals. This is not a clinically validated tool or medical
advice.

## Current status

The project generates linked patient, arrival, triage, treatment-start, and
departure records. Treatment uses finite ED capacity. Each run writes
`patients.csv`, `events.jsonl`, `encounters.csv`, `arrival_snapshots.csv`,
`arrival_training.csv`, `hospital_kpis.csv`, `hospital_daily_kpis.csv`, and
`manifest.json`.

There are two generator versions:

- **Version 1 is the default.** It independently chooses a patient ID for
  each arrival. This preserves the data used for the existing waiting-time,
  admission, and four-hour breach experiments, but can produce overlapping
  visits and misleading apparent return rates.
- **Version 2 is opt-in** with `--generator-version 2`. It assigns patients
  through a visit registry, permits intentional returns only after ED
  departure, and prevents a patient from having overlapping ED encounters.

The manifest records the generator version. For version 2, it also records
the return probability per arrival slot, return window, and number of
repeated visits. Existing model benchmarks have **not** been rerun on
version-two data.

Arrival snapshots use only events strictly earlier than each arrival. The
offline training table joins completed outcomes to arrival-known features.
Its target columns are labels, not predictors.

## Generate and audit a version-two run

From the project folder in PowerShell, using the existing virtual
environment:

```powershell
$env:PYTHONPATH = (Resolve-Path .\src).Path
$v2Run = "data/generated/flow-v2-14d-$(Get-Date -Format yyyyMMdd-HHmmss)"

.\.venv\Scripts\python.exe -m edflow --output $v2Run --start 2025-01-01T00:00:00+00:00 --hours 336 --patients 40000 --seed 42 --generator-version 2 --return-probability 0.1
.\.venv\Scripts\python.exe -m edflow.representation_audit --run $v2Run
```

The output directory must be new for each run. Omitting
`--generator-version 2` selects the original version-one generator.

The 14-day version-two run above produced 2,839 encounters and 11,356
events. Its audit found:

| Measure | Result |
| --- | ---: |
| Patients with encounters | 2,546 |
| Overlapping arrivals | 0 |
| Eligible discharged seven-day follow-ups | 873 |
| Censored discharged follow-ups | 896 |
| Admitted ED departures excluded as index visits | 1,070 |
| Apparent seven-day returns among eligible visits | 217 |
| Apparent return rate among eligible visits | 24.86% |

The eligible, censored, and admitted groups add up to all 2,839
encounters. The manifest reports 293 repeated visits across the full run;
that is a different measure from the 217 eligible seven-day returns. The
synthetic return process is a generator setting, not a calibrated estimate
of patient risk. No re-presentation prediction model has been evaluated yet.

## Local dashboard

`python -m edflow.dashboard --run <run-directory>` starts a read-only
dashboard at `http://127.0.0.1:8765/`. It displays run totals, hospital
KPIs, and daily KPIs with a hospital filter. The server binds to the local
computer and reads generated files; it does not change them.

The JSON endpoints are `/health`, `/api/manifest`, `/api/hospitals`, and
`/api/daily`. The daily endpoint accepts an optional `hospital_id` query
parameter. Press Ctrl+C in the terminal to stop the server.

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

Both runs used version one with `--hours 336 --patients 1000`. These are
synthetic, single-split results, not clinical performance claims.

Subgroup diagnostics by hospital and arrival mode are included in the model
report. The model improves overall MAE on both runs, but some hospital
groups are slightly worse than the global median. Seed 42's H03 group
retains a high 62.97-minute MAE despite improving on its 79.67-minute
baseline. These synthetic subgroup results are exploratory.

## Admission prediction experiments

At arrival, an admission classifier was compared with a baseline that
predicts the training-set admission rate. Both were evaluated on a
chronological holdout. Encounters whose departure outcome was unavailable
at the split were excluded from training.

| Seed | Eligible train | Test | Prevalence Brier | Arrival model Brier |
| --- | ---: | ---: | ---: | ---: |
| 42 | 2,249 | 568 | 0.2429 | 0.2555 |
| 73 | 2,237 | 570 | 0.2366 | 0.2470 |

Lower Brier scores are better. The arrival-time model did not beat the
prevalence baseline on either of these synthetic runs. Triage category is
unavailable at arrival, so it is not used by that model.

A separate post-triage experiment compares the prevalence baseline, an
admission-rate baseline for each triage category, and a regularized
logistic regression using arrival-known features plus triage category. All
three use the same chronological holdout. Training uses only admission
outcomes known before the holdout begins.

| Seed | Eligible train | Test | Prevalence Brier | Category Brier | Logistic Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| 42 | 2,249 | 568 | 0.2429 | 0.2041 | 0.2044 |
| 73 | 2,237 | 570 | 0.2366 | 0.1749 | 0.1800 |
| 13 | 2,224 | 566 | ~0.24 | ~0.19 | ~0.18 |
| 101 | 2,274 | 578 | ~0.23 | ~0.19 | ~0.18 |
| 202 | 2,268 | 575 | ~0.24 | ~0.19 | ~0.19 |

All five runs used version one with `--hours 336 --patients 1000`.
Values marked `~` were copied from a PowerShell table that displayed two
decimal places. The category baseline narrowly beats logistic regression
on seeds 42 and 73; logistic regression appears better at the displayed
precision on seeds 13 and 101. The rounded seed 202 scores do not
establish which is better. Both post-triage approaches improve on
prevalence in these synthetic runs. More validation is needed before
selecting a preferred model.

## Four-hour breach prediction experiment

A four-hour breach means the encounter's arrival-to-departure time exceeds
240 minutes. The arrival-time baseline predicts the breach rate among
eligible training encounters. A histogram gradient boosting classifier
uses only arrival-known features. Both are scored on the same
chronological holdout using Brier score. A training encounter is eligible
only if its departure outcome was known before the holdout begins.

| Seed | Eligible train | Test | Test breach rate | Baseline Brier | Model Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| 42 | 2,249 | 568 | 0.4613 | 0.2534 | 0.2170 |
| 73 | 2,237 | 570 | 0.4070 | 0.2414 | 0.2382 |
| 13 | 2,224 | 566 | 0.4470 | 0.2484 | 0.2198 |
| 101 | 2,274 | 578 | 0.4308 | 0.2467 | 0.2270 |
| 202 | 2,268 | 575 | 0.3843 | 0.2381 | 0.2425 |

All five runs used version one with `--hours 336 --patients 1000`. The
model beats the prevalence baseline on four runs, but is worse on seed
202. The gain on seed 73 is small. These repeated synthetic runs come from
the same simulator; they do not establish performance on real hospital
data.

## Re-presentation data quality

The version-one generator independently chooses patient IDs for arrivals.
Earlier 14-day checks found 104 and 85 overlapping arrivals with a pool of
1,000 patients (seeds 42 and 73), and 2 and 6 overlaps with a pool of
40,000 patients. Random ID reuse also changed the apparent return rate
sharply. Those old rates are not suitable as prediction labels.

Version two prevents overlapping ED visits in the tested 14-day run. Its
audit excludes admitted ED departures as index visits because ED departure
is not an inpatient discharge. It also separates visits with a full
seven-day follow-up window from visits censored by the end of the run. A
later arrival counts as an apparent return only when it occurs after
departure and within seven days.

These checks improve the synthetic representation, but do not establish
clinical validity. Before training a re-presentation model, validate
version two across more seeds and patient-pool sizes, define the target
population and prediction point, and rerun earlier model benchmarks on
version-two data.

## Planned capabilities

- Further validation of version-two generation and seven-day
  re-presentation labels
- Broader historical analytics and model validation
- Expanded dashboard and API
- Local event streaming and selective, cost-conscious cloud deployment

All hospitals, patients, encounters, and results are synthetic.