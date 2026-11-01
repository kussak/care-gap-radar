"""SQL for the API endpoints. Reads only marts and ml.risk_scores."""

import json

from api.db import fetch_all, fetch_one, metrics_path
from ml.features import FLAG_FEATURES

CONDITION_FLAGS = [f for f in FLAG_FEATURES if f.startswith("has_")]


def load_metrics() -> dict | None:
    path = metrics_path()
    return json.loads(path.read_text()) if path.exists() else None


def data_as_of():
    row = fetch_one("select data_as_of from marts.mart_population_summary")
    return row["data_as_of"] if row else None


def population_summary() -> dict | None:
    return fetch_one("select * from marts.mart_population_summary")


ORDER_BY = {
    # patients a care manager can act on (open gaps) first, then by predicted risk
    "gaps": "len(p.open_gap_codes) > 0 desc, r.risk_score desc nulls last, p.patient_id",
    "risk": "r.risk_score desc nulls last, p.patient_id",
}


def worklist(
    limit: int, offset: int, gap: str | None, min_risk: float | None, sort: str = "gaps"
) -> tuple[int, list[dict]]:
    where, params = ["true"], []
    if gap:
        where.append("list_contains(p.open_gap_codes, ?)")
        params.append(gap)
    if min_risk is not None:
        where.append("r.risk_percentile >= ?")
        params.append(min_risk)
    base = f"""
        from marts.mart_patient_current p
        left join ml.risk_scores r using (patient_id)
        where {' and '.join(where)}
    """
    total = fetch_one(f"select count(*) as n {base}", params)["n"]
    rows = fetch_all(
        f"""
        select p.patient_id, p.display_name, p.age_years as age, p.sex, p.payer_category,
               r.risk_score, r.risk_percentile, p.open_gap_codes, p.ed_visits_12m
        {base}
        order by {ORDER_BY[sort]}
        limit ? offset ?
        """,
        [*params, limit, offset],
    )
    return total, rows


def patient_detail(patient_id: str) -> dict | None:
    """Everything shown on the detail page, or None for an unknown patient."""
    row = fetch_one(
        """
        select p.*, r.risk_score, r.risk_percentile, r.top_drivers::varchar as top_drivers,
               r.model_version
        from marts.mart_patient_current p
        left join ml.risk_scores r using (patient_id)
        where p.patient_id = ?
        """,
        [patient_id],
    )
    if row is None:
        return None
    gaps = fetch_all(
        """
        select gap_code, gap_description, evidence, last_relevant_date
        from marts.mart_care_gaps_current where patient_id = ? order by gap_code
        """,
        [patient_id],
    )
    risk = None
    if row["risk_score"] is not None:
        risk = {
            "score": row["risk_score"],
            "percentile": row["risk_percentile"],
            "model_version": row["model_version"],
            "top_drivers": json.loads(row["top_drivers"]),
        }
    return {
        "patient_id": row["patient_id"],
        "display_name": row["display_name"],
        "age": row["age_years"],
        "sex": row["sex"],
        "payer_category": row["payer_category"],
        "race": row["race"],
        "ethnicity": row["ethnicity"],
        "data_as_of": row["index_date"],
        "conditions": [FLAG_FEATURES[f] for f in CONDITION_FLAGS if row[f]],
        "active_med_count": row["active_med_count"],
        "utilization": {
            k: row[k]
            for k in (
                "ed_visits_12m", "ed_visits_24m", "inpatient_visits_12m", "urgent_care_visits_12m",
                "outpatient_visits_12m", "total_claim_cost_12m", "days_since_last_encounter",
            )
        },
        "open_gaps": gaps,
        "risk": risk,
    }
