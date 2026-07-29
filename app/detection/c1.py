"""CDC EARS C1 detection.

This is a placeholder implementation with the correct interface and the
fixed baseline-contamination bug (the baseline window excludes the most
recent 7 days so a live outbreak can't poison its own baseline).

Replace the body of `run_c1` with your validated implementation from the
outbreak-ews Streamlit project (github.com/gathokib/outbreak-ews) — the
signature below is what app/pipeline/routes.py calls, so as long as you
keep the same inputs/outputs everything upstream keeps working.
"""

import numpy as np
import pandas as pd


def run_c1(df: pd.DataFrame, threshold: float = 2.0) -> pd.DataFrame:
    """
    df: must have columns ['date', 'cases'] sorted ascending by date.
    threshold: number of standard deviations above the 7-day baseline mean
               that counts as an alert (matches config.C1_ALERT_THRESHOLD).

    Returns a DataFrame with columns ['date', 'cases', 'expected', 'c1_score', 'is_alert'].
    """
    df = df.sort_values("date").reset_index(drop=True)

    baseline_window = 7
    guard_band = 2  # excludes the 2 most recent days from the baseline calc

    expected = []
    scores = []
    for i in range(len(df)):
        start = max(0, i - baseline_window - guard_band)
        end = max(0, i - guard_band)
        baseline = df["cases"].iloc[start:end]

        if len(baseline) < 3:
            expected.append(np.nan)
            scores.append(np.nan)
            continue

        mean = baseline.mean()
        std = baseline.std(ddof=0) or 1e-6
        expected.append(mean)
        scores.append((df["cases"].iloc[i] - mean) / std)

    df["expected"] = expected
    df["c1_score"] = scores
    df["is_alert"] = df["c1_score"] >= threshold
    return df
