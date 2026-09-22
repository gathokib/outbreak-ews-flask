"""Load surveillance observations from the application database."""

import pandas as pd
from sqlalchemy import func

from app.extensions import db
from app.models import Observation


def load_country_data(country: str) -> pd.DataFrame:
    """Load a country's surveillance observations from the database.

    Returns a DataFrame with the same columns expected by the
    detection algorithms: date and cases.
    """

    observations = (
        Observation.query
        .filter(
            func.lower(Observation.country) == country.strip().lower()
        )
        .order_by(Observation.observation_date.asc())
        .all()
    )

    if not observations:
        raise ValueError(
            f"No observations found in the database for '{country}'."
        )

    df = pd.DataFrame(
        [
            {
                "date": observation.observation_date,
                "cases": observation.cases,
            }
            for observation in observations
        ]
    )

    df["date"] = pd.to_datetime(df["date"])
    df["cases"] = pd.to_numeric(df["cases"], errors="raise")

    return (
        df[["date", "cases"]]
        .sort_values("date")
        .reset_index(drop=True)
    )


def available_countries() -> list:
    """Return countries that have surveillance observations in the database."""

    countries = (
        db.session.query(Observation.country)
        .distinct()
        .order_by(Observation.country.asc())
        .all()
    )

    return [country[0] for country in countries]