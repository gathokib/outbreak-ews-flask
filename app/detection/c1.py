"""CDC EARS C1 detection.

Validated implementation ported from the outbreak-ews Streamlit project
(github.com/gathokib/outbreak-ews, src/ears_detector.py — ears_c1_lagged).
Baseline window = 7 periods, lagged by 2 periods so a live outbreak can't
poison its own baseline. Achieved a 25.6% false positive rate on the
validated Kenya dataset, detecting all 3 known outbreak waves.
"""

import numpy as np
import pandas as pd


def run_c1(df: pd.DataFrame, threshold: float = 2.0) -> pd.DataFrame:
    """
    df: must have columns ['date', 'cases'] sorted ascending by date.
    threshold: number of standard deviations above the lagged baseline mean
               that counts as an alert (matches config.C1_ALERT_THRESHOLD).

    Returns a DataFrame with columns ['date', 'cases', 'expected', 'c1_score', 'is_alert'].
    """
    df = df.sort_values("date").reset_index(drop=True)

    window = 7
    lag = 2

    values = df["cases"].values
    n = len(values)

    expected = np.full(n, np.nan)
    c1_score = np.full(n, np.nan)

    for i in range(n):
        end = i - lag
        start = end - window
        if start < 0 or end <= 0:
            continue
        baseline_values = values[start:end]
        if len(baseline_values) < window:
            continue

        bmean = np.mean(baseline_values)
        bstd = np.std(baseline_values, ddof=1)
        if bstd < 0.1:
            bstd = 0.1

        expected[i] = bmean
        c1_score[i] = (values[i] - bmean) / bstd

    df["expected"] = expected
    df["c1_score"] = c1_score
    df["is_alert"] = df["c1_score"] >= threshold
    return df
