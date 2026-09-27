import io
import json

import pandas as pd
import pdfplumber
import requests

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from flask_login import login_required

from app.extensions import db
from app.models import Observation, Country


data_management_bp = Blueprint(
    "data_management",
    __name__,
    url_prefix="/data",
)


def get_country_coordinates(country_name):
    """Get geographic coordinates for a country using OpenStreetMap."""

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": country_name,
                "format": "json",
                "limit": 1,
                "featuretype": "country",
            },
            headers={
                "User-Agent": "Outbreak-EWS/1.0",
            },
            timeout=10,
        )

        response.raise_for_status()

        results = response.json()

        if results:
            return (
                float(results[0]["lat"]),
                float(results[0]["lon"]),
            )

    except Exception:
        pass

    return None, None


def _safe_csv_value(value):
    """Prevent spreadsheet formula injection in exported text fields."""

    if value is None:
        return value

    value = str(value)

    if value.startswith(("=", "+", "-", "@")):
        return "'" + value

    return value


def _load_uploaded_file(uploaded_file, extension):
    """
    Load CSV, Excel, or JSON surveillance data into a pandas DataFrame.
    """

    if extension == ".csv":
        return pd.read_csv(uploaded_file)

    if extension == ".xlsx":
        return pd.read_excel(uploaded_file)

    if extension == ".pdf":
        return _load_pdf_file(uploaded_file)

    if extension == ".json":
        raw_data = json.load(uploaded_file)

        # Support JSON files containing:
        # 1. A list of records
        # 2. {"data": [...]}
        # 3. {"observations": [...]}
        if isinstance(raw_data, list):
            records = raw_data

        elif isinstance(raw_data, dict):
            if isinstance(raw_data.get("data"), list):
                records = raw_data["data"]

            elif isinstance(raw_data.get("observations"), list):
                records = raw_data["observations"]

            else:
                raise ValueError(
                    "JSON must contain a list of records or a "
                    "'data'/'observations' array."
                )

        else:
            raise ValueError(
                "JSON must contain a list of surveillance records."
            )

        return pd.DataFrame(records)

    raise ValueError("Unsupported file format.")

def _load_pdf_file(uploaded_file):
    """
    Extract surveillance data from a structured PDF table.

    Expected table columns:
    - date
    - cases
    """

    records = []

    with pdfplumber.open(uploaded_file) as pdf:

        for page in pdf.pages:

            tables = page.extract_tables()

            for table in tables:

                if not table:
                    continue

                headers = [
                    str(column).strip().lower()
                    if column is not None
                    else ""
                    for column in table[0]
                ]

                if "date" not in headers or "cases" not in headers:
                    continue

                date_index = headers.index("date")
                cases_index = headers.index("cases")

                for row in table[1:]:

                    if not row:
                        continue

                    if len(row) <= max(
                        date_index,
                        cases_index,
                    ):
                        continue

                    records.append(
                        {
                            "date": row[date_index],
                            "cases": row[cases_index],
                        }
                    )

    if not records:
        raise ValueError(
            "No valid surveillance table was found in the PDF. "
            "The PDF must contain 'date' and 'cases' columns."
        )

    return pd.DataFrame(records)

def _validate_and_prepare_data(df, file_type):
    """
    Validate and prepare uploaded surveillance data.

    Required columns:
    - date
    - cases
    """

    required_columns = {"date", "cases"}

    # Make column names consistent.
    df.columns = [
        str(column).strip().lower()
        for column in df.columns
    ]

    if not required_columns.issubset(df.columns):

        missing = required_columns - set(df.columns)

        raise ValueError(
            f"Invalid {file_type} file. Missing column(s): "
            f"{', '.join(sorted(missing))}."
        )

    df = df[["date", "cases"]].copy()

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    )

    df["cases"] = pd.to_numeric(
        df["cases"],
        errors="coerce",
    )

    invalid_rows = (
        df["date"].isna()
        | df["cases"].isna()
        | (df["cases"] < 0)
    )

    invalid_count = int(invalid_rows.sum())

    df = df[~invalid_rows].copy()

    if df.empty:
        raise ValueError(
            f"The {file_type} file contains no valid "
            "surveillance records."
        )

    return df, invalid_count


@data_management_bp.route("/")
@login_required
def index():

    countries = (
        db.session.query(Observation.country)
        .distinct()
        .order_by(Observation.country.asc())
        .all()
    )

    countries = [country[0] for country in countries]

    observations = (
        Observation.query
        .order_by(Observation.observation_date.desc())
        .all()
    )

    return render_template(
        "data_management/index.html",
        countries=countries,
        observations=observations,
    )


@data_management_bp.route("/import", methods=["POST"])
@login_required
def import_data():

    uploaded_file = request.files.get("file")
    country = request.form.get("country", "").strip()
    disease = request.form.get("disease", "COVID-19").strip()

    if not uploaded_file or uploaded_file.filename == "":
        flash(
            "Please select a CSV, Excel, JSON or PDF file.",
            "danger",
        )
        return redirect(url_for("data_management.index"))

    filename = uploaded_file.filename
    extension = filename.lower().rsplit(".", 1)[-1]

    extension = f".{extension}"

    supported_extensions = {
        ".csv": "CSV",
        ".xlsx": "Excel",
        ".json": "JSON",
        ".pdf": "PDF",
    }

    if extension not in supported_extensions:
        flash(
            "Unsupported file format. Please upload a "
            "CSV, Excel (.xlsx), JSON file or PDF file.",
            "danger",
        )
        return redirect(url_for("data_management.index"))

    if not country:
        flash(
            "Please enter a country.",
            "danger",
        )
        return redirect(url_for("data_management.index"))

    if not disease:
        flash(
            "Please enter a disease name.",
            "danger",
        )
        return redirect(url_for("data_management.index"))

    file_type = supported_extensions[extension]

    try:

        df = _load_uploaded_file(
            uploaded_file,
            extension,
        )

        df, invalid_count = _validate_and_prepare_data(
            df,
            file_type,
        )

        imported = 0
        duplicates = 0

        for _, row in df.iterrows():

            observation_date = row["date"].date()
            cases = float(row["cases"])

            existing = Observation.query.filter_by(
                disease=disease,
                country=country,
                location=country,
                observation_date=observation_date,
                source=filename,
            ).first()

            if existing:
                duplicates += 1
                continue

            observation = Observation(
                disease=disease,
                country=country,
                location=country,
                observation_date=observation_date,
                cases=cases,
                deaths=None,
                latitude=None,
                longitude=None,
                source=filename,
            )

            db.session.add(observation)

            imported += 1

        # Find or create the country record.
        existing_country = Country.query.filter_by(
            name=country
        ).first()

        if not existing_country:

            latitude, longitude = get_country_coordinates(
                country
            )

            new_country = Country(
                name=country,
                latitude=latitude,
                longitude=longitude,
                current_risk_level="normal",
            )

            db.session.add(new_country)

        elif (
            existing_country.latitude is None
            or existing_country.longitude is None
        ):

            latitude, longitude = get_country_coordinates(
                country
            )

            existing_country.latitude = latitude
            existing_country.longitude = longitude

        db.session.commit()

        message = (
            f"{file_type} import complete: "
            f"{imported} record(s) imported, "
            f"{duplicates} duplicate(s) skipped."
        )

        if invalid_count:
            message += (
                f" {invalid_count} invalid row(s) skipped."
            )

        flash(message, "success")

    except ValueError as exc:

        db.session.rollback()

        flash(
            str(exc),
            "danger",
        )

    except Exception as exc:

        db.session.rollback()

        flash(
            f"Import failed. Please check the {file_type} "
            "file format.",
            "danger",
        )

    return redirect(url_for("data_management.index"))


@data_management_bp.route("/export")
@login_required
def export_data():

    country = request.args.get("country", "").strip()

    query = Observation.query

    if country:
        query = query.filter_by(country=country)

    observations = (
        query
        .order_by(
            Observation.country.asc(),
            Observation.observation_date.asc(),
        )
        .all()
    )

    rows = [
        {
            "disease": _safe_csv_value(observation.disease),
            "country": _safe_csv_value(observation.country),
            "location": _safe_csv_value(observation.location),
            "date": observation.observation_date.isoformat(),
            "cases": observation.cases,
            "deaths": observation.deaths,
            "latitude": observation.latitude,
            "longitude": observation.longitude,
            "source": _safe_csv_value(observation.source),
        }
        for observation in observations
    ]

    df = pd.DataFrame(rows)

    if df.empty:

        df = pd.DataFrame(
            columns=[
                "disease",
                "country",
                "location",
                "date",
                "cases",
                "deaths",
                "latitude",
                "longitude",
                "source",
            ]
        )

    output = io.BytesIO()

    df.to_csv(
        output,
        index=False,
    )

    output.seek(0)

    filename = (
        f"{country.lower().replace(' ', '_')}_"
        f"surveillance_export.csv"
        if country
        else "surveillance_export.csv"
    )

    return send_file(
        output,
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )

