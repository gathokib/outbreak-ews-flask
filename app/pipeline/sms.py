"""Africa's Talking SMS notification service."""

import requests
from flask import current_app


def send_alert_sms(to_number: str, message: str) -> bool:
    """Send an SMS alert through Africa's Talking."""

    api_key = current_app.config.get("AT_API_KEY")
    username = current_app.config.get("AT_USERNAME", "sandbox")

    if not api_key:
        current_app.logger.warning(
            "AT_API_KEY not set — skipping SMS send."
        )
        return False

    if not to_number:
        current_app.logger.warning(
            "ALERT_RECIPIENT not set — skipping SMS send."
        )
        return False

    url = "https://api.sandbox.africastalking.com/version1/messaging"

    headers = {
        "apiKey": api_key,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }

    data = {
        "username": username,
        "to": to_number,
        "message": message,
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            data=data,
            timeout=10,
        )

        response.raise_for_status()

        result = response.json()

        recipient = result["SMSMessageData"]["Recipients"][0]

        if recipient.get("status") == "Success":
            current_app.logger.info(
                f"SMS sent successfully to {to_number}. "
                f"Message ID: {recipient.get('messageId')}"
            )
            return True

        current_app.logger.error(
            f"SMS delivery failed: {result}"
        )
        return False

    except Exception as exc:
        current_app.logger.error(
            f"SMS send failed: {exc}"
        )
        return False