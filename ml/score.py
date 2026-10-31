"""Score the current index date and write ml.risk_scores with the top SHAP drivers per patient."""

import json
from datetime import datetime, timezone

import duckdb
import joblib
import numpy as np
import pandas as pd
import shap

from ml.features import FEATURE_LABELS, MODEL_PATH, WAREHOUSE, encode, format_value, load_features

TOP_N_DRIVERS = 3


def top_drivers(x_row: pd.Series, shap_row: np.ndarray) -> list[dict]:
    order = np.argsort(-np.abs(shap_row))[:TOP_N_DRIVERS]
    return [
        {
            "feature": x_row.index[i],
            "label": FEATURE_LABELS[x_row.index[i]],
            "value": float(x_row.iloc[i]),
            "display_value": format_value(x_row.index[i], float(x_row.iloc[i])),
            "shap": round(float(shap_row[i]), 4),
            "direction": "up" if shap_row[i] > 0 else "down",
        }
        for i in order
    ]


def main() -> None:
    artifact = joblib.load(MODEL_PATH)
    model, model_version = artifact["model"], artifact["model_version"]

    current = load_features(["current"])
    X = encode(current)[artifact["features"]]
    risk = model.predict_proba(X)[:, 1]
    # SHAP values for a binary GBM are in log-odds; positive pushes risk up.
    shap_values = shap.TreeExplainer(model).shap_values(X)

    scored_at = datetime.now(timezone.utc).replace(tzinfo=None)
    scores = pd.DataFrame(
        {
            "patient_id": current["patient_id"],
            "risk_score": risk.round(4),
            "risk_percentile": (pd.Series(risk).rank(pct=True) * 100).round(1),
            "top_drivers": [
                json.dumps(top_drivers(X.iloc[i], shap_values[i])) for i in range(len(X))
            ],
            "model_version": model_version,
            "scored_at": scored_at,
        }
    )

    with duckdb.connect(str(WAREHOUSE)) as con:
        con.execute("create schema if not exists ml")
        con.execute("""
            create or replace table ml.risk_scores as
            select patient_id, risk_score, risk_percentile, top_drivers::json as top_drivers,
                   model_version, scored_at
            from scores
        """)
        n = con.execute("select count(*) from ml.risk_scores").fetchone()[0]

    print(f"Wrote {n} rows to ml.risk_scores ({model_version}).")


if __name__ == "__main__":
    main()
