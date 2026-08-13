from flask import current_app
from app.extensions import db
from app.models import PipelineRun, Alert, Country, utcnow
from app.pipeline.data_loader import load_country_data
from app.pipeline.sms import send_alert_sms
from app.detection.c1 import run_c1
from app.detection.isolation_forest import run_isolation_forest


def process_country(
    country: str,
    method: str = "c1",
    user_id: int | None = None,
):
    """
    Run outbreak detection for a country.

    This contains the core pipeline logic so it can be called by:
    - the Flask manual pipeline route
    - an automatic scheduler
    - an Azure Function/job later
    """

    # Create a pipeline run
    run = PipelineRun(
        user_id=user_id,
        country=country,
        detection_method=method,
        status="running",
    )

    db.session.add(run)
    db.session.commit()

    try:
        # 1. Load surveillance data
        df = load_country_data(country)

        # 2. Run detection model
        if method == "isolation_forest":
            result = run_isolation_forest(
                df,
                contamination=current_app.config["ISOFOREST_CONTAMINATION"],
            )
            score_col = "anomaly_score"
        else:
            result = run_c1(
                df,
                threshold=current_app.config["C1_ALERT_THRESHOLD"],
            )
            score_col = "c1_score"

        # 3. Select detected alerts
        alert_rows = result[result["is_alert"] == True]  # noqa: E712

        alerts_created = 0
        sms_sent = 0

        # 4. Create alerts
        for _, row in alert_rows.iterrows():

            severity = (
                "high"
                if row[score_col] >= 3
                else "medium"
            )

            alert = Alert(
                pipeline_run_id=run.id,
                country=country,
                alert_date=row["date"].date(),
                metric_value=float(row["cases"]),
                threshold_value=current_app.config["C1_ALERT_THRESHOLD"],
                severity=severity,
            )

            db.session.add(alert)
            alerts_created += 1

            # 5. Send SMS for high-severity alerts
            if severity == "high":

                from flask import current_app

                recipient = current_app.config.get(
                    "ALERT_RECIPIENT",
                    "",
                )

                sent = send_alert_sms(
                    to_number=recipient,
                    message=(
                        f"[Outbreak EWS] "
                        f"High-severity alert for "
                        f"{country} on "
                        f"{row['date'].date()}"
                    ),
                )

                alert.sms_sent = sent

                if sent:
                    sms_sent += 1

        # 6. Update pipeline run
        run.rows_processed = len(df)
        run.status = "completed"
        run.completed_at = utcnow()

        # 7. Update country risk level
        refresh_country_risk(country)

        db.session.commit()

        return {
            "success": True,
            "run_id": run.id,
            "country": country,
            "rows_processed": len(df),
            "alerts_created": alerts_created,
            "sms_sent": sms_sent,
        }

    except Exception as exc:
        db.session.rollback()

        run.status = "failed"
        run.error_message = str(exc)

        db.session.add(run)
        db.session.commit()

        return {
            "success": False,
            "run_id": run.id,
            "country": country,
            "error": str(exc),
        }


def refresh_country_risk(country_name: str):
    """
    Recalculate the cached risk level for a country.
    """

    country = Country.query.filter_by(
        name=country_name
    ).first()

    if country is None:
        country = Country(name=country_name)
        db.session.add(country)

    latest_alert = (
        Alert.query
        .filter_by(country=country_name)
        .order_by(Alert.created_at.desc())
        .first()
    )

    if latest_alert is None:
        country.current_risk_level = "normal"

    elif latest_alert.severity == "high":
        country.current_risk_level = "high"

    else:
        country.current_risk_level = "elevated"

    country.last_alert_id = (
        latest_alert.id
        if latest_alert
        else None
    )

    country.last_updated = utcnow()