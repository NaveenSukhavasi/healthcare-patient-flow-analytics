# Intelligent Emergency Department Patient Flow Platform

A software engineering and data science portfolio project built around fully
synthetic emergency department activity at fictional Victorian-style hospitals.

## Current status

The validated event contract, reproducible arrival generator, and linked
synthetic patient generator are implemented. Each run writes `patients.csv`,
`events.jsonl`, and `manifest.json`. Triage, treatment queues, outcomes,
models, API, streaming, web interface, and cloud deployment remain planned.

## Planned capabilities

- Reproducible patient-flow simulation and historical analytics
- Arrival-time operational features with checks against data leakage
- Waiting-time, admission, breach-risk, and re-presentation modelling
- Tested API and a usable web interface
- Local event streaming and selective, cost-conscious cloud deployment

This is a synthetic portfolio system, not a clinically validated tool or
medical advice.