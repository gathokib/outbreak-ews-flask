"""Isolation Forest detection.

Validated implementation ported from the outbreak-ews Streamlit project
(github.com/gathokib/outbreak-ews, src/ml_detector.py). Uses the same
engineered features (rolling mean, growth rate, deviation from baseline,
growth acceleration, sustained elevation) and standard scaling before
fitting Isolation Forest, which achieved a 3.9% false positive rate on
the validated Kenya dataset.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


def _engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d["rolling_mean_4w"] = d["cases"].rolling(4, min_periods=2).mean()
    d["growth_rate"] = d["cases"].pct_change() * 100
    rolling_8w = d["cases"].rolling(8, min_periods=4).mean()
    d["deviation_from_baseline"] = d["cases"] - rolling_8w
    d["growth_acceleration"] = d["growth_rate"].diff()
    d["sustained_elevation"] = d["cases"].rolling(3, min_periods=2).sum()
    return d


FEATURES = [
    "cases",
    "rolling_mean_4w",
    "growth_rate",
    "deviation_from_baseline",
    "growth_acceleration",
    "sustained_elevation",
]


def run_isolation_forest(df: pd.DataFrame, contamination: float = 0.05) -> pd.DataFrame:
    """
    df: must have columns ['date', 'cases'] sorted ascending by date.
    contamination: expected proportion of anomalies (matches
                   config.ISOFOREST_CONTAMINATION).

    Returns a DataFrame with columns ['date', 'cases', 'anomaly_score', 'is_alert'].
    Rows before the rolling-feature windows fill (first ~7 periods) can't
    be scored and are dropped, same as the validated Streamlit pipeline.
    """
    df = df.sort_values("date").reset_index(drop=True)
    engineered = _engineer_features(df)

    clean = engineered.dropna(subset=[
        "rolling_mean_4w", "growth_rate",
        "deviation_from_baseline", "growth_acceleration",
        "sustained_elevation",
    ]).copy().reset_index(drop=True)

    X = clean[FEATURES].values
    X = np.where(np.isinf(X), 0, X)
    X = np.where(np.isnan(X), 0, X)

    X_scaled = StandardScaler().fit_transform(X)

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
        max_samples="auto",
    )
    model.fit(X_scaled)

    raw_predictions = model.predict(X_scaled)
    anomaly_scores = -model.score_samples(X_scaled)  # higher = more anomalous

    clean["anomaly_score"] = anomaly_scores
    clean["is_alert"] = raw_predictions == -1

    return clean[["date", "cases", "anomaly_score", "is_alert"]]
