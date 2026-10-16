# Re-presentation generator design and validation

## Why version two was needed

The original generator assigns a patient ID independently to each
arrival. It can assign the same patient while that patient is still in
an ED encounter. Earlier 14-day version-one runs found overlapping
arrivals:

| Seed | Patient pool | Overlapping arrivals |
| --- | ---: | ---: |
| 42 | 1,000 | 104 |
| 73 | 1,000 | 85 |
| 42 | 40,000 | 2 |
| 73 | 40,000 | 6 |

Random ID reuse also made apparent return rates highly sensitive to
patient-pool size. Version-one apparent returns are not suitable as
re-presentation prediction labels. Version one remains the default
generator so earlier model experiments remain reproducible.

## Implemented version-two flow

Version two is selected with `--generator-version 2`.

1. Generate arrival slots containing a time, hospital, and arrival
   mode, without assigning patient IDs.
2. Process arrivals, triage completions, treatment starts, and
   departures in chronological order.
3. Assign a previously unused patient to a first visit, or choose an
   eligible previously discharged patient for an intentional return.
4. Keep active patients in a visit registry. A patient cannot receive
   another arrival while an ED encounter is active, including at a
   different hospital.
5. Release a patient at ED departure. Only a discharged patient can
   become eligible for an intentional return, strictly after
   departure and within seven days.
6. Apply the configured return probability at each arrival slot when
   an eligible discharged patient exists. If no return is chosen,
   assign a previously unused patient. Fail clearly if the pool
   cannot support the arrival.
7. Derive encounter rows from the four events for each completed
   visit. Record the generator version and return settings in the
   run manifest.

The probability is a synthetic arrival-slot setting. With
`--return-risk-weighting`, eligible return candidates are selected using
synthetic chronic-condition count. Neither mode represents an individual's
calibrated clinical risk. An admitted patient's ED
departure is not an inpatient discharge, so admission does not make
that patient eligible for a generated return.

## Seven-day audit rules

A discharged ED encounter is an eligible index visit only when the
observation window contains all seven days after its departure. A
later ED arrival for the same patient counts as an apparent return
when it occurs strictly after the index departure and no more than
seven days later.

A discharged encounter with less than seven days of observation is
censored. An admitted ED departure is excluded as an index visit
because the simulation has no inpatient discharge time. The eligible,
censored, and admitted counts must add up to all encounters. The
audit also counts arrivals that overlap an earlier active encounter
for the same patient.

An apparent return is an observed pattern in synthetic data. It is
not a clinically validated diagnosis, risk estimate, or model label
ready for deployment.

## Validated 14-day version-two run

The CLI generated a run beginning 2025-01-01 at 00:00 UTC, lasting
336 hours, with 40,000 synthetic patients, seed 42, and a configured
return probability of 0.1 per arrival slot.

| Measure | Result |
| --- | ---: |
| Encounters | 2,839 |
| Events | 11,356 |
| Patients with encounters | 2,546 |
| Overlapping arrivals | 0 |
| Eligible discharged seven-day follow-ups | 873 |
| Censored discharged follow-ups | 896 |
| Admitted ED departures excluded as index visits | 1,070 |
| Apparent seven-day returns among eligible visits | 217 |
| Apparent return rate among eligible visits | 24.86% |
| Repeated visits recorded in the manifest | 293 |

The event count is four per encounter. The audit groups reconcile:
873 + 896 + 1,070 = 2,839. The 293 repeated visits cover the whole
run; the 217 apparent returns count only eligible seven-day index
visits. These are different measures.

The full CLI run matches the earlier direct-function validation for
this configuration. It establishes that the tested scenario has no
overlapping ED encounters. It does not establish that its return
rate represents real patients.

## Additional checks and model evaluation

Implemented checks cover chronological event generation, patient
assignment without overlapping visits, return eligibility after
departure, pool exhaustion, repeatability from seeds, encounter-row
construction, seven-day follow-up boundaries, and CLI output. The
existing waiting-time, admission, breach, and dashboard tests also
pass with the version-two code present. Additional 14-day audits with
seeds 13 and 73 found zero overlapping arrivals. A 40,000-patient run
with return probability zero had zero apparent returns; raising the
probability to 0.05 produced 117 eligible apparent returns. These are
synthetic sensitivity checks, not calibration to observed patients.

The 28-day weighted version-two evaluation uses ED departure as the
prediction point. It excludes admitted and censored visits, purges
pre-split visits whose seven-day labels were not known at the split,
and compares a classifier with a training-prevalence baseline on later
visits. With seed 42 it trained on 855 visits, purged 872, and tested
on 936. The classifier reached ROC AUC 0.6072 but Brier score 0.1717,
worse than baseline Brier score 0.1416. The full report is in
`representation_model_result.json`.

This model is experimental. Its synthetic return process is not
clinically calibrated, its probabilistic accuracy did not beat baseline
in this run, and the older waiting-time, admission, and breach
benchmarks still need re-evaluation on version-two data before any
cross-version comparison.
