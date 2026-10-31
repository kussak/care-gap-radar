"""Shared feature definitions for training and scoring.

The feature list, human-readable labels and value formatting live here and only here, so the
model, the SHAP drivers, the API and the LLM facts all describe features the same way.
"""

from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
MODEL_DIR = ROOT / "ml" / "models"
MODEL_PATH = MODEL_DIR / "model.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"

NUMERIC_FEATURES = {
    "age_years": "Age",
    "ed_visits_12m": "ED visits (12 mo)",
    "ed_visits_24m": "ED visits (24 mo)",
    "inpatient_visits_12m": "Inpatient stays (12 mo)",
    "urgent_care_visits_12m": "Urgent care visits (12 mo)",
    "outpatient_visits_12m": "Outpatient/primary care visits (12 mo)",
    "total_claim_cost_12m": "Total claim cost (12 mo)",
    "days_since_last_encounter": "Days since last visit",
    "active_med_count": "Active medications",
}

FLAG_FEATURES = {
    "has_diabetes": "Diabetes",
    "has_hypertension": "Hypertension",
    "has_chf": "Heart failure",
    "has_copd": "COPD",
    "has_asthma": "Asthma",
    "has_ckd": "Chronic kidney disease",
    "has_depression": "Depression",
    "has_obesity": "Obesity",
    "gap_dm_a1c": "Overdue A1c test",
    "gap_htn_bp": "Blood pressure not controlled/measured",
}

# Categorical columns, one-hot encoded with fixed categories so train and score always align.
CATEGORIES = {
    "sex": {"f": "Female", "m": "Male"},
    "payer_category": {
        "medicaid": "Medicaid",
        "medicare": "Medicare",
        "private": "Private insurance",
        "none_other": "Uninsured/other",
    },
}

ONE_HOT_FEATURES = {
    f"{col}_{value}": label for col, values in CATEGORIES.items() for value, label in values.items()
}

FEATURES = [*NUMERIC_FEATURES, *FLAG_FEATURES, *ONE_HOT_FEATURES]
FEATURE_LABELS = {**NUMERIC_FEATURES, **FLAG_FEATURES, **ONE_HOT_FEATURES}
LABEL = "label_ed_6m"


def format_value(feature: str, value: float) -> str:
    """Human-readable feature value for UI and LLM facts."""
    if feature in FLAG_FEATURES or feature in ONE_HOT_FEATURES:
        return "yes" if value >= 0.5 else "no"
    if feature == "total_claim_cost_12m":
        return f"${value:,.0f}"
    return f"{value:,.0f}"


def encode(df: pd.DataFrame) -> pd.DataFrame:
    """Build the model matrix (columns in FEATURES order) from raw feature rows."""
    out = df[[*NUMERIC_FEATURES, *FLAG_FEATURES]].astype(float).copy()
    for col, values in CATEGORIES.items():
        for value in values:
            out[f"{col}_{value}"] = (df[col] == value).astype(float)
    return out[FEATURES]


def load_features(index_names: list[str], with_labels: bool = False) -> pd.DataFrame:
    """Load int_patient_features rows (optionally joined to labels) for the given index dates."""
    label_join = (
        "join intermediate.int_labels l using (patient_id, index_name)" if with_labels else ""
    )
    label_col = f", l.{LABEL}" if with_labels else ""
    sql = f"""
        select f.*{label_col}
        from intermediate.int_patient_features f
        {label_join}
        where f.index_name in (select unnest(?))
        order by f.index_name, f.patient_id
    """
    with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
        return con.execute(sql, [index_names]).df()
