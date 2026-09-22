from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
import pandas as pd

from app.models import Country
from app.pipeline.data_loader import load_country_data
from app.detection.c1 import run_c1
from app.detection.isolation_forest import run_isolation_forest


surveillance_bp = Blueprint(
    "surveillance",
    __name__,
    url_prefix="/surveillance",
)


@surveillance_bp.route("/")
@login_required
def index():
    countries = Country.query.order_by(Country.name).all()

    return render_template(
        "surveillance/index.html",
        countries=countries,
    )


@surveillance_bp.route("/api/timeseries")
@login_required
def timeseries():
    """
    Return surveillance observations together with C1 baseline
    and Isolation Forest anomaly results.
    """

    country = request.args.get("country", "").strip()

    if not country:
        return jsonify({
            "error": "Country is required."
        }), 400

    try:
        # Load observations from the database
        df = load_country_data(country)

        # Run C1 statistical detection
        c1_result = run_c1(
            df,
            threshold=2.0,
        )

        # Run Isolation Forest ML detection
        ml_result = run_isolation_forest(
            df,
            contamination=0.05,
        )

        # Convert dates to strings for JSON
        labels = [
            date.strftime("%Y-%m-%d")
            for date in df["date"]
        ]

        # Map C1 results by date
        c1_by_date = {
            row["date"].strftime("%Y-%m-%d"): row
            for _, row in c1_result.iterrows()
        }

        # Map ML results by date
        ml_by_date = {
            row["date"].strftime("%Y-%m-%d"): row
            for _, row in ml_result.iterrows()
        }

        expected = []
        c1_alerts = []
        ml_anomalies = []

        for date in labels:
            c1_row = c1_by_date.get(date)
            ml_row = ml_by_date.get(date)

            # C1 expected value.
            # Return null instead of NaN because NaN is not valid JSON.
            if (
                c1_row is None
                or pd.isna(c1_row["expected"])
            ):
                expected.append(None)
            else:
                expected.append(
                    float(c1_row["expected"])
                )

            # C1 alert status
            c1_alerts.append(
                False
                if c1_row is None
                else bool(c1_row["is_alert"])
            )

            # Isolation Forest anomaly status
            ml_anomalies.append(
                False
                if ml_row is None
                else bool(ml_row["is_alert"])
            )

        return jsonify({
            "country": country,
            "labels": labels,
            "cases": [
                float(value)
                for value in df["cases"]
            ],
            "expected": expected,
            "c1_alerts": c1_alerts,
            "ml_anomalies": ml_anomalies,
        })

    except ValueError:
        return jsonify({
            "error": "No surveillance data found for this country."
        }), 404

    except Exception:
        return jsonify({
            "error": "Unable to load surveillance data."
        }), 500