from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from app import create_app
from app.extensions import db
from app.models import Observation


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

COUNTRY_FILES = {
    "Kenya": DATA_DIR / "kenya.csv",
    "Ethiopia": DATA_DIR / "ethiopia.csv",
    "Tanzania": DATA_DIR / "tanzania.csv",
    "Uganda": DATA_DIR / "uganda.csv",
}


def import_country(country, csv_path):
    print(f"\nImporting {country}...")

    if not csv_path.exists():
        print(f"ERROR: File not found: {csv_path}")
        return 0

    df = pd.read_csv(csv_path)

    required_columns = {"date", "cases"}

    if not required_columns.issubset(df.columns):
        raise ValueError(
            f"{csv_path.name} must contain columns: date,cases"
        )

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["cases"] = pd.to_numeric(df["cases"], errors="coerce")

    invalid_rows = df["date"].isna() | df["cases"].isna()

    if invalid_rows.any():
        invalid_count = invalid_rows.sum()
        raise ValueError(
            f"{country}: {invalid_count} invalid row(s) found."
        )

    df = df.sort_values("date")

    imported = 0
    skipped = 0

    for _, row in df.iterrows():
        observation_date = row["date"].date()
        cases = float(row["cases"])

        existing = Observation.query.filter_by(
            disease="COVID-19",
            country=country,
            location=None,
            observation_date=observation_date,
            source=csv_path.name,
        ).first()

        if existing:
            skipped += 1
            continue

        observation = Observation(
            disease="COVID-19",
            country=country,
            location=None,
            observation_date=observation_date,
            cases=cases,
            deaths=0,
            source=csv_path.name,
        )

        db.session.add(observation)
        imported += 1

    db.session.commit()

    print(f"  Imported: {imported}")
    print(f"  Skipped:  {skipped}")

    return imported


def main():
    app = create_app()

    with app.app_context():
        total_imported = 0

        for country, csv_path in COUNTRY_FILES.items():
            total_imported += import_country(country, csv_path)

        print("\n-----------------------------")
        print(f"Total imported: {total_imported}")
        print("-----------------------------")


if __name__ == "__main__":
    main()