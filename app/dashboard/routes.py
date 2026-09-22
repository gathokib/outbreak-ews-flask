from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Country, PipelineRun, Alert, Observation


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/")


@dashboard_bp.route("/")
@login_required
def index():
    # Countries currently represented in the surveillance database
    countries = (
        Country.query
        .order_by(Country.name)
        .all()
    )

    # If a country has observations but no Country record yet,
    # make sure it still appears on the dashboard.
    observation_countries = (
        db.session.query(Observation.country)
        .distinct()
        .order_by(Observation.country)
        .all()
    )

    existing_names = {country.name for country in countries}

    for row in observation_countries:
        country_name = row[0]

        if country_name not in existing_names:
            country = Country(
                name=country_name,
                current_risk_level="normal",
            )
            db.session.add(country)
            countries.append(country)

    db.session.commit()

    countries.sort(key=lambda country: country.name)

    # Dashboard statistics
    total_observations = Observation.query.count()
    total_alerts = Alert.query.count()

    high_alerts = (
        Alert.query
        .filter(Alert.severity == "high")
        .count()
    )

    medium_alerts = (
        Alert.query
        .filter(Alert.severity == "medium")
        .count()
    )

    # Most recent alerts
    recent_alerts = (
        Alert.query
        .order_by(Alert.alert_date.desc(), Alert.created_at.desc())
        .limit(8)
        .all()
    )

    # Most recent pipeline executions
    recent_runs = (
        PipelineRun.query
        .order_by(PipelineRun.started_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "dashboard/index.html",
        countries=countries,
        total_observations=total_observations,
        total_alerts=total_alerts,
        high_alerts=high_alerts,
        medium_alerts=medium_alerts,
        recent_alerts=recent_alerts,
        recent_runs=recent_runs,
    )