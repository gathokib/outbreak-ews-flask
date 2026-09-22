import io

import pandas as pd
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
from app.models import Observation


data_management_bp = Blueprint(
    "data_management",
    __name__,
    url_prefix="/data",
)


def _safe_csv_value(value):
    """Prevent spreadsheet formula injection in exported text fields."""
    if value is None:
        return value

    value = str(value)

    if value.startswith(("=", "+", "-", "@")):
        return "'" + value

    return value


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

    return render_template(
        "data_management/index.html",
        countries=countries,
    )


@data_management_bp.route("/import", methods=["POST"])
@login_required
def import_data():
    uploaded_file = request.files.get("file")
    country = request.form.get("country", "").strip()
    disease = request.form.get("disease", "COVID-19").strip()

    if not uploaded_file or uploaded_file.filename == "":
        flash("Please select a CSV file.", "danger")
        return redirect(url_for("data_management.index"))

    if not uploaded_file.filename.lower().endswith(".csv"):
        flash("Only CSV files are supported.", "danger")
        return redirect(url_for("data_management.index"))

    if not country:
        flash("Please select a country.", "danger")
        return redirect(url_for("data_management.index"))

    if not disease:
        flash("Please enter a disease name.", "danger")
        return redirect(url_for("data_management.index"))

    try:
        df = pd.read_csv(uploaded_file)

        required_columns = {"date", "cases"}

        if not required_columns.issubset(df.columns):
            missing = required_columns - set(df.columns)

            flash(
                f"Invalid CSV. Missing column(s): "
                f"{', '.join(sorted(missing))}.",
                "danger",
            )

            return redirect(url_for("data_management.index"))

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
            flash(
                "The CSV contains no valid surveillance records.",
                "danger",
            )
            return redirect(url_for("data_management.index"))

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
                source=uploaded_file.filename,
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
                source=uploaded_file.filename,
            )

            db.session.add(observation)
            imported += 1

        db.session.commit()

        message = (
            f"Import complete: {imported} record(s) imported, "
            f"{duplicates} duplicate(s) skipped."
        )

        if invalid_count:
            message += f" {invalid_count} invalid row(s) skipped."

        flash(message, "success")

    except Exception:
        db.session.rollback()

        flash(
            "Import failed. Please check the CSV format and try again.",
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