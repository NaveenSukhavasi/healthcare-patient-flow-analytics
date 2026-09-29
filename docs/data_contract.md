# Emergency Department Data and Event Contract

Status: local synthetic patient-flow generator implemented; prediction models and deployment remain planned.

All hospitals, patients, and encounters in this project are synthetic.
Store event timestamps in UTC. Derive Victorian local time from
Australia/Melbourne when needed for reporting or features.

## Core records

### Hospital
- hospital_id: stable unique ID
- hospital_name: fictional name
- region: metropolitan, regional, or rural
- peer_group: synthetic comparison group
- bed_capacity: total hospital beds
- ed_treatment_spaces: places available for ED treatment

Hospital beds and ED treatment spaces are different measures.

### Patient
- patient_id: stable synthetic ID
- demographic fields: sex, Indigenous status, socioeconomic quintile,
  and remoteness for later cohort analysis
- chronic_condition_count: synthetic count

Age is calculated at each encounter, rather than stored as a permanent
patient attribute.

### Encounter
- encounter_id, patient_id, hospital_id
- arrival_at, arrival_mode
- triage_at, triage_category, presentation_group
- treatment_start_at
- departure_at, departure_status, admitted_flag

Later outcome columns, such as waiting time and four-hour breach, are
derived from these timestamps. An encounter is complete only after departure.

## Event sequence

Each encounter produces timestamped events:

1. arrival
2. triage_completed
3. treatment_started
4. departure

An event has event_id, encounter_id, hospital_id, occurred_at,
event_type, schema_version, and an event-specific payload.

The arrival event may contain arrival mode. Triage category becomes
available only at triage_completed. Admission and departure outcome
become available only at departure.

## Prediction cutoffs

### At arrival
The first waiting-time, admission, and four-hour breach predictions use
only information available at or before arrival: patient history known
then, arrival mode, hospital, calendar features, and hospital workload
calculated from earlier events.

The arrival snapshot is recorded before the new arrival changes the
hospital's workload counts. It must not contain triage category,
treatment start, departure, admission outcome, or future activity.

### After triage
A separate future prediction may use triage category. Its target should
be clearly defined, for example remaining time until treatment starts.

## Labels and validation

- waiting_time_minutes = treatment_start_at - arrival_at
- ed_length_of_stay_minutes = departure_at - arrival_at
- four_hour_breach = ed_length_of_stay_minutes > 240
- admission label comes from the completed encounter
- seven_day_representation requires a later encounter for the same patient;
  encounters without a full seven-day observation window cannot be labelled
  as confirmed non-representations

IDs must be unique where required, references must exist, timestamps
must follow event order, and durations and workload counts cannot be
negative. The simulator must be reproducible from a recorded seed.

These synthetic labels and demographic results are not clinically
validated and must not be presented as real hospital performance.