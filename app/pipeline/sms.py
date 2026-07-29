"""Africa's Talking SMS wrapper.

Isolated in its own module so a missing API key or a network failure
never crashes a pipeline run — detection and alerting must succeed even
if notification doesn't. Import errors and send failures are caught and
logged rather than raised.
"""

from flask import current_app


def send_alert_sms(to_number: str, message: str) -> bool:
    api_key = current_app.config.get("AT_API_KEY")
    if not api_key:
        current_app.logger.warning("AT_API_KEY not set — skipping SMS send (dev mode).")
        return False

    try:
        import africastalking

        africastalking.initialize(current_app.config["AT_USERNAME"], api_key)
        sms = africastalking.SMS
        sms.send(message, [to_number])
        return True
    except Exception as exc:  # noqa: BLE001 — deliberately broad: SMS failure must not break the pipeline
        current_app.logger.error(f"SMS send failed: {exc}")
        return False
