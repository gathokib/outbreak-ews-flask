from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.models import PipelineRun, Alert
from app.pipeline.processor import process_country
from app.pipeline.data_loader import available_countries


pipeline_bp = Blueprint(
    "pipeline",
    __name__,
    url_prefix="/pipeline",
)


@pipeline_bp.route("/")
@login_required
def index():
    runs = (
        PipelineRun.query
        .order_by(PipelineRun.started_at.desc())
        .limit(20)
        .all()
    )

    countries = available_countries()

    return render_template(
        "pipeline/index.html",
        runs=runs,
        countries=countries,
    )


@pipeline_bp.route("/run", methods=["POST"])
@login_required
def trigger_run():
    """Run outbreak detection for a selected country."""

    country = request.form.get("country", "").strip()
    method = request.form.get("method", "c1")

    if not country:
        flash("Please select a country.", "danger")
        return redirect(url_for("pipeline.index"))

    result = process_country(
        country=country,
        method=method,
        user_id=current_user.id,
    )

    if result["success"]:
        flash(
            f"Pipeline run completed — "
            f"{result['alerts_created']} new alert(s) detected.",
            "success",
        )
    else:
        flash(
            f"Pipeline run failed: {result['error']}",
            "danger",
        )

    return redirect(
        url_for(
            "pipeline.view_run",
            run_id=result["run_id"],
        )
    )


@pipeline_bp.route("/run/<int:run_id>")
@login_required
def view_run(run_id):
    run = db.session.get(PipelineRun, run_id)

    if run is None:
        flash("Run not found.", "danger")
        return redirect(url_for("pipeline.index"))

    alerts = (
        run.alerts
        .order_by(Alert.alert_date)
        .all()
    )

    return render_template(
        "pipeline/run_detail.html",
        run=run,
        alerts=alerts,
    )