import os
import httpx

SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '')


def send_slack_alert(text: str) -> None:
    if not SLACK_WEBHOOK_URL:
        return
    try:
        httpx.post(SLACK_WEBHOOK_URL, json={'text': text}, timeout=5)
    except Exception:
        pass
