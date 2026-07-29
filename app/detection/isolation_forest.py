"""Isolation Forest detection.

Placeholder implementation with the correct interface — replace the body
with your validated model from the outbreak-ews Streamlit project. Keep
the same inputs/outputs so app/pipeline/routes.py doesn't need to change.
"""

import pandas as pd
from sklearn.ensemble import IsolationForest


def run_isolation_forest(df: pd.DataFrame, contamination: float = 0.05) -> pd.DataFrame:
    """
    df: must have columns ['date', 'cases'] sorted ascending by date.
    contamination: expected proportion of anomalies (matches
                   config.ISOFOREST_CONTAMINATION — 0.05 reflects your
                   validated 3.9% false-positive result plus headroom).

    Returns a DataFrame with columns ['date', 'cases', 'anomaly_score', 'is_alert'].
    """
    df = df.sort_values("date").reset_index(drop=True)

    features = df[["cases"]].copy()
    features["rolling_mean_7"] = df["cases"].rolling(7, min_periods=1).mean()
    features["diff"] = df["cases"].diff().fillna(0)

    model = IsolationForest(contamination=contamination, random_state=42)
    model.fit(features)

    df["anomaly_score"] = -model.decision_function(features)  # higher = more anomalous
    df["is_alert"] = model.predict(features) == -1
    return df
