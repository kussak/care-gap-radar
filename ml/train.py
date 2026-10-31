"""Train the 6-month ED-visit risk model and compare it with a prior-ED-count baseline.

Time-based split: fit on the `train` index date, evaluate on the later `test` index date.
"""

import json
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score

from ml.features import (
    FEATURES,
    LABEL,
    METRICS_PATH,
    MODEL_DIR,
    MODEL_PATH,
    encode,
    load_features,
)


def top_decile_capture(y: np.ndarray, score: np.ndarray) -> float:
    """Share of all positives that land in the top 10% of patients by score."""
    n_top = max(1, int(len(score) * 0.10))
    top = np.argsort(-score, kind="stable")[:n_top]
    return float(y[top].sum() / y.sum())


def auroc_delta_ci(y: np.ndarray, model: np.ndarray, baseline: np.ndarray, n_boot: int = 2000) -> list[float]:
    """95% paired-bootstrap CI for AUROC(model) - AUROC(baseline) on the same test patients."""
    rng = np.random.default_rng(42)
    deltas = []
    for _ in range(n_boot):
        i = rng.integers(0, len(y), len(y))
        if 0 < y[i].sum() < len(i):
            deltas.append(roc_auc_score(y[i], model[i]) - roc_auc_score(y[i], baseline[i]))
    return [round(float(np.percentile(deltas, q)), 4) for q in (2.5, 97.5)]


def evaluate(y: np.ndarray, score: np.ndarray) -> dict:
    return {
        "auroc": round(roc_auc_score(y, score), 4),
        "pr_auc": round(average_precision_score(y, score), 4),
        "top_decile_capture": round(top_decile_capture(y, score), 4),
    }


def main() -> None:
    df = load_features(["train", "test"], with_labels=True)
    train, test = df[df.index_name == "train"], df[df.index_name == "test"]
    X_train, y_train = encode(train), train[LABEL].to_numpy()
    X_test, y_test = encode(test), test[LABEL].to_numpy()

    model = GradientBoostingClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=3,
        subsample=0.8,
        min_samples_leaf=20,
        random_state=42,
    )
    model.fit(X_train, y_train)

    model_scores = model.predict_proba(X_test)[:, 1]
    # Baseline: rank by prior-12-month ED count; ED-24m breaks ties so the ranking isn't mostly ties.
    baseline_scores = test["ed_visits_12m"].to_numpy() + test["ed_visits_24m"].to_numpy() / 1000

    trained_at = datetime.now(timezone.utc)
    model_version = f"gbm-{trained_at:%Y%m%d%H%M}"
    metrics = {
        "model_version": model_version,
        "trained_at": trained_at.isoformat(timespec="seconds"),
        "train_index_date": str(train.index_date.iloc[0].date()),
        "test_index_date": str(test.index_date.iloc[0].date()),
        "n_train": int(len(train)),
        "n_test": int(len(test)),
        "base_rate_train": round(float(y_train.mean()), 4),
        "base_rate_test": round(float(y_test.mean()), 4),
        "model": evaluate(y_test, model_scores),
        "baseline_prior_ed": evaluate(y_test, baseline_scores),
    }
    # Only claim a win when the whole 95% CI of the AUROC improvement is above zero.
    metrics["auroc_delta_ci95"] = auroc_delta_ci(y_test, model_scores, baseline_scores)
    metrics["beats_baseline"] = metrics["auroc_delta_ci95"][0] > 0

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "features": FEATURES, "model_version": model_version}, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2) + "\n")

    print(f"train {metrics['train_index_date']}  n={metrics['n_train']}  base rate {metrics['base_rate_train']:.1%}")
    print(f"test  {metrics['test_index_date']}  n={metrics['n_test']}  base rate {metrics['base_rate_test']:.1%}")
    print(f"\n{'':22}{'AUROC':>8}{'PR-AUC':>8}{'top-10% capture':>17}")
    for name, key in [("GBM model", "model"), ("Baseline (prior ED)", "baseline_prior_ed")]:
        m = metrics[key]
        print(f"{name:22}{m['auroc']:>8.3f}{m['pr_auc']:>8.3f}{m['top_decile_capture']:>17.1%}")
    lo, hi = metrics["auroc_delta_ci95"]
    verdict = "beats" if metrics["beats_baseline"] else "does NOT clearly beat"
    print(f"\nAUROC improvement over baseline: 95% CI [{lo:+.3f}, {hi:+.3f}]")
    print(f"Model {verdict} the baseline. Saved {MODEL_PATH.name} ({model_version}).")


if __name__ == "__main__":
    main()
