"""Canonical filesystem paths. Everything under DATA_DIR and OUTPUTS_DIR is git-ignored."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
PHYSIONET_DIR = DATA_DIR / "physionet.org" / "files"
MIMIC_NOTE_DIR = PHYSIONET_DIR / "mimic-iv-note" / "2.2" / "note"
MIMIC_HOSP_DIR = PHYSIONET_DIR / "mimiciv" / "3.1" / "hosp"

DISCHARGE_NOTES = MIMIC_NOTE_DIR / "discharge.csv.gz"
# Optional Parquet copy (created in notebooks/data_exploration.ipynb); much faster to query.
DISCHARGE_PARQUET = DATA_DIR / "parquet" / "discharge.parquet"
ADMISSIONS = MIMIC_HOSP_DIR / "admissions.csv.gz"
DIAGNOSES_ICD = MIMIC_HOSP_DIR / "diagnoses_icd.csv.gz"

# Derived MIMIC data (samples, parquet caches, splits). Still DUA-covered.
DERIVED_DIR = DATA_DIR / "derived"

# Model outputs, judge scores, hand labels. Also MIMIC-derived.
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
