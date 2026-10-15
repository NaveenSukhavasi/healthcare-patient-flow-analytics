# Re-presentation generator design

## Problem found

The current arrival generator selects a patient ID independently for every
arrival. It does not know whether that patient is still in the emergency
department. The re-presentation audit found overlapping encounters in all
four 14-day runs tested.

| Seed | Patient pool | Overlapping arrivals | Apparent seven-day return rate |
| --- | ---: | ---: | ---: |
| 42 | 1,000 | 104 | 76.65% |
| 73 | 1,000 | 85 | 77.65% |
| 42 | 40,000 | 2 | 3.52% |
| 73 | 40,000 | 6 | 3.81% |

The large change with patient-pool size shows that random ID reuse controls
the apparent return rate. None of these runs supplies a trustworthy
re-presentation prediction label.

## Version-two generation flow

1. Generate proposed arrival times, hospitals, and arrival modes without
   assigning patient IDs.
2. Process arrivals, triage, treatment starts, and departures in one
   chronological event queue.
3. Keep a set of patients with an active encounter. An arriving patient must
   not be in that set.
4. For a first visit, choose a patient who has not previously presented in
   the run.
5. For an intentional return, choose a previously discharged patient who is
   not active. Set a configurable return probability and record the choice
   in the run manifest.
6. If the available patient pool cannot support the requested arrival
   volume and return probability, fail with a clear error or generate more
   patients. Do not silently reuse an active patient.
7. Record every patient's arrival and departure history so the generator
   and audit can verify the sequence.

An admitted patient's ED departure is not a hospital discharge. Until the
simulation includes inpatient discharge times, admitted encounters should
not be used as index visits for a seven-day ED return label.

## Evaluation rules

A seven-day label is eligible only when the index encounter has ended and
the run contains the full seven days after its departure. A later ED arrival
for the same patient counts as a return only if it occurs strictly after
that departure and no more than seven days later.

Chronological model training must use labels that became known before the
holdout starts. Patient history used as a predictor must contain only
events known at the prediction time.

## Acceptance checks

- The audit reports zero overlapping arrivals across several seeds.
- A deliberately scheduled return occurs after the earlier departure.
- A patient still in an encounter cannot be selected for another arrival,
  even at a different hospital.
- A too-small patient pool produces a clear result rather than forced ID
  reuse.
- The same configuration and seeds reproduce identical output.
- Seven-day labels correctly handle the exact boundary and incomplete
  follow-up.
- The manifest identifies the generator version and return-process
  settings.
- Existing waiting, admission, breach, and dashboard tests pass.
- Model benchmarks are rerun and documented because version-two data will
  differ from the current generator.