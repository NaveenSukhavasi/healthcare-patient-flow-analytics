# Emergency Department Data and Event Contract

Status: local synthetic patient-flow generators, dashboard, and offline
waiting-time, admission, and four-hour breach experiments are implemented.
Generator version 2 is opt-in. Deployment and re-presentation prediction
remain planned.

All hospitals, patients, and encounters in this project are synthetic.
Store event timestamps in UTC. Derive Victorian local time from
Australia/Melbourne when needed for reporting or features.

## Generator versions

Version 1 is the default. It selects a patient ID independently for each
arrival. This can create overlapping visits for one patient, so its
apparent re-presentation rates must not be used as prediction labels.

Version 2 is selected with `--generator-version 2`. It generates arrival
slots before assigning patients, processes ED events chronologically, and
uses a visit registry to prevent overlapping encounters. A return may
select a previously discharged patient only after their ED departure and
within seven days. Admitted patients are not made returnable by their ED
departure. If the patient pool cannot support an arrival, generation
fails rather than assigning an active patient.

The version-two return probability applies to an arrival slot when an
eligible discharged patient exists. It is a synthetic generator setting,
not a calibrated patient-level probability.

## Core records

### Hospital

- `hospital_id`: stable unique ID
- `hospital_name`: fictional name
- `region`: metropolitan, regional, or rural
- `bed_capacity`: total hospital beds
- `ed_treatment_spaces`: places available for ED treatment
- `base_arrivals_per_hour`: synthetic arrival-demand setting

Hospital beds and ED treatment spaces are different measures.

### Patient

- `patient_id`: stable synthetic ID
- `birth_date`
- `sex`, `indigenous_status`, `socioeconomic_quintile`, and `remoteness`:
  synthetic demographic fields
- `chronic_condition_count`: synthetic count

Age is calculated at each encounter, rather than stored as a permanent
patient attribute.

### Encounter

- `encounter_id`, `patient_id`, `hospital_id`
- `arrival_at`, `arrival_mode`
- `triage_at`, `triage_category`, `presentation_group`
- `treatment_start_at`
- `departure_at`, `departure_status`, `admitted_flag`
- `waiting_time_minutes`, `ed_length_of_stay_minutes`,
  `four_hour_breach`: derived outcomes

An encounter is complete only after departure. In version 2, a patient
cannot begin another ED encounter while one is active, even at a
different hospital.

## Event sequence

Each completed encounter produces four timestamped events:

1. `arrival`
2. `triage_completed`
3. `treatment_started`
4. `departure`

An event has `event_id`, `encounter_id`, `patient_id`, `hospital_id`,
`occurred_at`, `event_type`, `schema_version`, and an event-specific
`payload`.

The arrival payload contains arrival mode. Triage category and
presentation group become available only at `triage_completed`.
Admission and departure outcome become available only at `departure`.
Event schema version and generator version are separate concepts.

## Run files and manifest

A run writes `patients.csv`, `events.jsonl`, `encounters.csv`,
`arrival_snapshots.csv`, `arrival_training.csv`, `hospital_kpis.csv`,
`hospital_daily_kpis.csv`, and `manifest.json`.

The manifest records the run start, duration, seeds, hospitals, row
counts, and `generator_version`. A version-two manifest also records
`registry_seed`, `return_probability_per_arrival_slot`,
`return_window_days`, and `intentional_return_count`. The intentional
return count measures repeated visits in the full run; it is not the
same as the count of eligible seven-day return labels.

## Prediction cutoffs

### At arrival

Waiting-time, admission, and four-hour breach experiments use only
information available at or before arrival: patient history known
then, arrival mode, hospital, calendar features, and hospital workload
calculated from earlier events.

The arrival snapshot is recorded before the new arrival changes the
hospital's workload counts. It must not contain triage category,
treatment start, departure, admission outcome, breach outcome, or
future activity.

### After triage

The post-triage admission experiment may use triage category together
with arrival-known features. It predicts the eventual admission
outcome, which is available only after departure. Triage category
must not be treated as an arrival-time feature.

## Labels and validation

- `waiting_time_minutes = treatment_start_at - arrival_at`
- `ed_length_of_stay_minutes = departure_at - arrival_at`
- `four_hour_breach = ed_length_of_stay_minutes > 240`
- The admission label comes from the completed encounter.

For an apparent seven-day ED re-presentation label, the index
encounter must end with ED discharge. An admitted patient's ED
departure is not an inpatient discharge and is excluded as an index
visit. A discharged index is eligible only when the observation window
includes the full seven days after its departure. A later arrival for
the same patient counts as an apparent return when it occurs strictly
after departure and no more than seven days later. A discharged visit
without a complete follow-up window is censored, not a confirmed
negative.

The audit reports eligible follow-ups, censored follow-ups, and
excluded admitted indices separately. These three counts must add up
to the encounter count. It also reports overlapping arrivals; version
two should report zero. Apparent return rates in synthetic data are
not clinical estimates.

Chronological model evaluations may train only on labels available
before the test period begins. Patient history used as a predictor
must include only events known at its prediction time. Encoders,
scalers, and models must be fitted on eligible training rows, never
on test rows.

IDs must be unique where required, references must exist, timestamps
must follow event order, and durations and workload counts cannot be
negative. A run must be reproducible from its recorded configuration
and seeds.

The existing waiting-time, admission, and breach benchmarks use
version-one data. They must be rerun before making claims about model
performance on version-two data. No re-presentation prediction model
has been evaluated yet.

These synthetic labels and demographic results are not clinically
validated and must not be presented as real hospital performance.