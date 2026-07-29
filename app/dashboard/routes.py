from flask import Blueprint, render_template
from flask_login import login_required

from app.models import Country, PipelineRun, Alert

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/")


@dashboard_bp.route("/")
@login_required
def index():
    countries = Country.query.order_by(Country.name).all()
    recent_runs = PipelineRun.query.order_by(PipelineRun.started_at.desc()).limit(5).all()
    alert_count_24h = Alert.query.count()  # simple placeholder count; refine with a time filter once you have real data
    return render_template(
        "dashboard/index.html",
        countries=countries,
        recent_runs=recent_runs,
        alert_count_24h=alert_count_24h,
    )
