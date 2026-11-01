"""Shared fixtures: a tiny warehouse, metrics file and brief cache in a temp dir; never the paid API."""

import json
from datetime import date

import duckdb
import pytest
from fastapi.testclient import TestClient

AS_OF = date(2026, 10, 30)

# Column -> DuckDB type for the fixture mart. test_contract.py checks these against the real mart.
PATIENT_COLUMNS = {
    "patient_id": "varchar", "index_date": "date", "age_years": "integer", "sex": "varchar",
    "payer_category": "varchar", "ed_visits_12m": "bigint", "inpatient_visits_12m": "bigint",
    "urgent_care_visits_12m": "bigint", "outpatient_visits_12m": "bigint", "ed_visits_24m": "bigint",
    "total_claim_cost_12m": "decimal(38,2)", "days_since_last_encounter": "bigint",
    "has_diabetes": "integer", "has_hypertension": "integer", "has_chf": "integer",
    "has_copd": "integer", "has_asthma": "integer", "has_ckd": "integer",
    "has_depression": "integer", "has_obesity": "integer", "active_med_count": "bigint",
    "gap_dm_a1c": "integer", "gap_htn_bp": "integer", "first_name": "varchar",
    "last_name": "varchar", "display_name": "varchar", "race": "varchar", "ethnicity": "varchar",
    "open_gap_codes": "varchar[]",
}

PATIENTS = [
    # A: 58 y/o woman with both gaps and the highest risk
    dict(patient_id="aaaa-1111", age_years=58, sex="f", payer_category="medicaid", ed_visits_12m=2,
         inpatient_visits_12m=1, urgent_care_visits_12m=0, outpatient_visits_12m=6, ed_visits_24m=3,
         total_claim_cost_12m=12345.67, days_since_last_encounter=12, has_diabetes=1,
         has_hypertension=1, active_med_count=7, gap_dm_a1c=1, gap_htn_bp=1,
         first_name="Testy123", last_name="Patient456", open_gap_codes=["DM_A1C", "HTN_BP"]),
    # B: 93 y/o man, no gaps, low risk (exercises the 90+ age band)
    dict(patient_id="bbbb-2222", age_years=93, sex="m", payer_category="medicare", ed_visits_12m=0,
         inpatient_visits_12m=0, urgent_care_visits_12m=0, outpatient_visits_12m=4, ed_visits_24m=0,
         total_claim_cost_12m=2100.0, days_since_last_encounter=40, active_med_count=3,
         first_name="Elder77", last_name="Oldman88", open_gap_codes=[]),
    # C: 34 y/o woman with an HTN gap, mid risk
    dict(patient_id="cccc-3333", age_years=34, sex="f", payer_category="private", ed_visits_12m=1,
         inpatient_visits_12m=0, urgent_care_visits_12m=2, outpatient_visits_12m=3, ed_visits_24m=1,
         total_claim_cost_12m=4000.0, days_since_last_encounter=100, has_hypertension=1,
         active_med_count=2, gap_htn_bp=1, first_name="Middle55", last_name="Case66",
         open_gap_codes=["HTN_BP"]),
]

GAPS = [
    ("aaaa-1111", "DM_A1C", "Diabetes: no HbA1c test in the past 12 months",
     "last A1c 2025-03-14 (7.2%)", date(2025, 3, 14)),
    ("aaaa-1111", "HTN_BP", "Hypertension: blood pressure uncontrolled (systolic >= 140) or not "
     "measured in the past 12 months", "last BP 152/94 on 2026-05-02", date(2026, 5, 2)),
    ("cccc-3333", "HTN_BP", "Hypertension: blood pressure uncontrolled (systolic >= 140) or not "
     "measured in the past 12 months", "no BP on record", None),
]

DRIVERS = [
    {"feature": "ed_visits_12m", "label": "ED visits (12 mo)", "value": 2.0, "display_value": "2",
     "shap": 0.8, "direction": "up"},
    {"feature": "age_years", "label": "Age", "value": 58.0, "display_value": "58", "shap": 0.3,
     "direction": "up"},
    {"feature": "payer_category_private", "label": "Private insurance", "value": 0.0,
     "display_value": "no", "shap": -0.1, "direction": "down"},
]
# bbbb (no gap) outranks cccc (gap) on risk, so the two sort orders differ
RISK = {"aaaa-1111": (0.31, 97.5), "bbbb-2222": (0.20, 85.0), "cccc-3333": (0.12, 80.0)}

METRICS = {
    "model_version": "gbm-test", "trained_at": "2026-10-31T00:00:00+00:00",
    "train_index_date": "2025-10-30", "test_index_date": "2026-04-30", "n_train": 100,
    "n_test": 100, "base_rate_train": 0.06, "base_rate_test": 0.06,
    "model": {"auroc": 0.56, "pr_auc": 0.09, "top_decile_capture": 0.16},
    "baseline_prior_ed": {"auroc": 0.54, "pr_auc": 0.10, "top_decile_capture": 0.15},
    "auroc_delta_ci95": [-0.04, 0.08], "beats_baseline": False,
}


def build_warehouse(path) -> None:
    con = duckdb.connect(str(path))
    con.execute("create schema marts; create schema ml")
    cols = ", ".join(f"{c} {t}" for c, t in PATIENT_COLUMNS.items())
    con.execute(f"create table marts.mart_patient_current ({cols})")
    for p in PATIENTS:
        row = {c: 0 for c in PATIENT_COLUMNS} | {"index_date": AS_OF, "race": "white",
                                                 "ethnicity": "nonhispanic"} | p
        row["display_name"] = f"{row['first_name']} {row['last_name']}"
        con.execute(
            f"insert into marts.mart_patient_current values ({', '.join('?' * len(PATIENT_COLUMNS))})",
            [row[c] for c in PATIENT_COLUMNS],
        )
    con.execute("""create table marts.mart_care_gaps_current (patient_id varchar, index_date date,
        gap_code varchar, gap_description varchar, evidence varchar, last_relevant_date date)""")
    for g in GAPS:
        con.execute("insert into marts.mart_care_gaps_current values (?, ?, ?, ?, ?, ?)",
                    [g[0], AS_OF, *g[1:]])
    con.execute("""create table marts.mart_population_summary as select
        date '2026-10-30' data_as_of, 3::bigint patient_count, 1::bigint gap_dm_a1c_count,
        2::bigint gap_htn_bp_count, 2::bigint patients_with_open_gaps, 1::bigint payer_medicaid,
        1::bigint payer_medicare, 1::bigint payer_private, 0::bigint payer_none_other,
        3::bigint ed_visits_12m, 1::bigint inpatient_visits_12m, 2::bigint urgent_care_visits_12m,
        13::bigint outpatient_visits_12m, 18445.67::decimal(38,2) total_claim_cost_12m""")
    con.execute("""create table ml.risk_scores (patient_id varchar, risk_score double,
        risk_percentile double, top_drivers json, model_version varchar, scored_at timestamp)""")
    for pid, (score, pct) in RISK.items():
        con.execute("insert into ml.risk_scores values (?, ?, ?, ?, 'gbm-test', now())",
                    [pid, score, pct, json.dumps(DRIVERS)])
    con.close()


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Point the API at fixture files and make any real Anthropic client construction fail."""
    warehouse = tmp_path / "warehouse.duckdb"
    build_warehouse(warehouse)
    metrics = tmp_path / "metrics.json"
    metrics.write_text(json.dumps(METRICS))
    monkeypatch.setenv("WAREHOUSE_PATH", str(warehouse))
    monkeypatch.setenv("METRICS_PATH", str(metrics))
    monkeypatch.setenv("BRIEF_CACHE_PATH", str(tmp_path / "app.sqlite"))
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    import anthropic

    def _no_real_client(*args, **kwargs):
        raise AssertionError("Tests must never construct a real Anthropic client")

    monkeypatch.setattr(anthropic.Anthropic, "__init__", _no_real_client)


@pytest.fixture
def fake_provider():
    from api.llm.fake_provider import FakeProvider

    return FakeProvider()


@pytest.fixture
def client(fake_provider):
    from api.llm.provider import get_provider
    from api.main import app

    app.dependency_overrides[get_provider] = lambda: fake_provider
    yield TestClient(app)
    app.dependency_overrides.clear()
