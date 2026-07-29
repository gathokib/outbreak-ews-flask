from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required

from app.models import Alert, Country

surveillance_bp = Blueprint("surveillance", __name__, url_prefix="/surveillance")


@surveillance_bp.route("/")
@login_required
def index():
    countries = Country.query.order_by(Country.name).all()
    return render_template("surveillance/index.html", countries=countries)


@surveillance_bp.route("/api/timeseries")
@login_required
def timeseries():
    """Returns alert history for one country as JSON, for Chart.js to consume.
    Kept as a separate JSON endpoint (rather than embedding data in the page)
    so the front end can re-query it when the user switches country without
    a full page reload."""
    country = request.args.get("country", "")
    query = Alert.query.order_by(Alert.alert_date)
    if country:
        query = query.filter_by(country=country)
    alerts = query.all()

    return jsonify(
        {
            "labels": [a.alert_date.isoformat() for a in alerts],
            "values": [a.metric_value for a in alerts],
            "thresholds": [a.threshold_value for a in alerts],
            "severities": [a.severity for a in alerts],
        }
    )
