from flask import Blueprint, render_template, request
from flask_login import login_required

from app.models import Alert

alerts_bp = Blueprint("alerts", __name__, url_prefix="/alerts")


@alerts_bp.route("/")
@login_required
def index():
    country = request.args.get("country", "")
    severity = request.args.get("severity", "")

    query = Alert.query
    if country:
        query = query.filter_by(country=country)
    if severity:
        query = query.filter_by(severity=severity)

    alerts = query.order_by(Alert.created_at.desc()).all()
    countries = sorted({a.country for a in Alert.query.all()})

    return render_template(
        "alerts/index.html", alerts=alerts, countries=countries, selected_country=country, selected_severity=severity
    )
