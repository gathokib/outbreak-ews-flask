"""Loads the case-count time series that a pipeline run detects on.

For the presentation build, this reads from data/<country>.csv (columns:
date, cases). Point this at your real OWID/JHU extract by dropping the
matching CSV into the data/ folder — nothing else in the pipeline needs
to change, since app/detection/*.py only cares about the ['date','cases']
shape, not where it came from.
"""

import os
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")


def load_country_data(country: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, f"{country.lower().replace(' ', '_')}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No data file for '{country}'. Expected {path} with columns 'date,cases'."
        )
    df = pd.read_csv(path, parse_dates=["date"])
    return df[["date", "cases"]].sort_values("date").reset_index(drop=True)


def available_countries() -> list:
    if not os.path.exists(DATA_DIR):
        return []
    return sorted(
        f[:-4].replace("_", " ").title()
        for f in os.listdir(DATA_DIR)
        if f.endswith(".csv")
    )
