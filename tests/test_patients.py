from datetime import date

import pytest

from edflow.patients import Patient, generate_patients


REFERENCE_DATE = date(2025, 1, 1)


def test_patient_generation_is_reproducible_with_unique_ids():
    first = generate_patients(2_000, seed=42, reference_date=REFERENCE_DATE)
    second = generate_patients(2_000, seed=42, reference_date=REFERENCE_DATE)

    assert [patient.to_record() for patient in first] == [
        patient.to_record() for patient in second
    ]
    assert len({patient.patient_id for patient in first}) == 2_000
    assert first[0].patient_id == "P000001"
    assert first[-1].patient_id == "P002000"


def test_chronic_conditions_have_an_age_relationship():
    patients = generate_patients(
        2_000, seed=42, reference_date=REFERENCE_DATE
    )
    younger = [
        patient.chronic_condition_count
        for patient in patients
        if patient.age_on(REFERENCE_DATE) < 40
    ]
    older = [
        patient.chronic_condition_count
        for patient in patients
        if patient.age_on(REFERENCE_DATE) >= 65
    ]

    assert sum(older) / len(older) > sum(younger) / len(younger)


def test_age_changes_on_birthday():
    patient = Patient(
        patient_id="P000001",
        birth_date=date(2000, 6, 15),
        sex="female",
        indigenous_status="unknown",
        socioeconomic_quintile=3,
        remoteness="regional",
        chronic_condition_count=0,
    )

    assert patient.age_on(date(2025, 6, 14)) == 24
    assert patient.age_on(date(2025, 6, 15)) == 25


def test_patient_count_must_be_positive():
    with pytest.raises(ValueError, match="positive"):
        generate_patients(0, seed=42, reference_date=REFERENCE_DATE)