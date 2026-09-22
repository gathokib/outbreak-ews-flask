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

    The pipeline:
    1. Loads surveillance observations from the database.
    2. Runs the selected detection method.
    3. Creates alerts for detected anomalies.
    4. Avoids duplicate alerts for the same country/date/method.
    5. Sends SMS for high-severity alerts.
    6. Updates the country's cached risk level.
    """

    if method not in {"c1", "isolation_forest"}:
        raise ValueError(
            "Unsupported detection method. "
            "Use 'c1' or 'isolation_forest'."
        )

    run = PipelineRun(
        user_id=user_id,
        country=country,
        detection_method=method,
        status="running",
    )

    db.session.add(run)
    db.session.commit()

    try:
        # 1. Load surveillance data from the database
        df = load_country_data(country)

        # 2. Run the selected detection method
        if method == "isolation_forest":
            result = run_isolation_forest(
                df,
                contamination=current_app.config[
                    "ISOFOREST_CONTAMINATION"
                ],
            )
            score_col = "anomaly_score"

        else:
            result = run_c1(
                df,
                threshold=current_app.config[
                    "C1_ALERT_THRESHOLD"
                ],
            )
            score_col = "c1_score"

        # 3. Select detected anomalies
        alert_rows = result[result["is_alert"]].copy()

        alerts_created = 0
        alerts_skipped = 0
        sms_sent = 0

        # 4. Create alerts
        for _, row in alert_rows.iterrows():

            alert_date = row["date"].date()

            # Prevent duplicate alerts when the same pipeline
            # is run again for the same country/date/method.
            existing_alert = Alert.query.filter_by(
                country=country,
                alert_date=alert_date,
                detection_method=method,
            ).first()

            if existing_alert:
                alerts_skipped += 1
                continue

            score = float(row[score_col])
            cases = float(row["cases"])

            # C1 scores are standard-deviation scores.
            # Isolation Forest scores are anomaly scores and
            # should NOT be compared against the C1 threshold.
            if method == "c1":
                threshold = float(
                    current_app.config["C1_ALERT_THRESHOLD"]
                )

                severity = (
                    "high"
                    if score >= 3.0
                    else "medium"
                )

                reason = (
                    f"Cases were {score:.2f} standard deviations "
                    f"above the expected C1 baseline."
                )

            else:
                # Isolation Forest already classified this row
                # as an anomaly. Severity is based on the anomaly
                # score, not the C1 threshold.
                threshold = 0.0

                severity = (
                    "high"
                    if score >= 0.70
                    else "medium"
                )

                reason = (
                    f"Isolation Forest identified an anomalous "
                    f"surveillance pattern with an anomaly score "
                    f"of {score:.3f}."
                )

            alert = Alert(
                pipeline_run_id=run.id,
                country=country,
                alert_date=alert_date,
                metric_value=cases,
                threshold_value=threshold,
                detection_method=method,
                reason=reason,
                severity=severity,
            )

            db.session.add(alert)
            alerts_created += 1

            # 5. Send SMS for high-severity alerts
            if severity == "high":

                recipient = current_app.config.get(
                    "ALERT_RECIPIENT",
                    "",
                )

                if recipient:
                    sent = send_alert_sms(
                        to_number=recipient,
                        message=(
                            f"[Outbreak EWS] "
                            f"High-severity {method.upper()} alert "
                            f"for {country} on {alert_date}"
                        ),
                    )

                    alert.sms_sent = sent

                    if sent:
                        sms_sent += 1

        # 6. Update pipeline run
        run.rows_processed = len(df)
        run.anomalies_detected = len(alert_rows)
        run.alerts_created = alerts_created
        run.alerts_skipped = alerts_skipped
        run.sms_sent = sms_sent
        run.status = "completed"
        run.completed_at = utcnow()

        # 7. Update country risk level
        refresh_country_risk(country)

        db.session.commit()

        return {
            "success": True,
            "run_id": run.id,
            "country": country,
            "method": method,
            "rows_processed": len(df),
            "anomalies_detected": len(alert_rows),
            "alerts_created": alerts_created,
            "alerts_skipped": alerts_skipped,
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
            "method": method,
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