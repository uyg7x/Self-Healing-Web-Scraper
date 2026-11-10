import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from core.config import EMAIL_CONFIG

logger = logging.getLogger(__name__)


class AlertSystem:

    def __init__(self):
        self.enabled = EMAIL_CONFIG.get("enabled", False)
        self.config = EMAIL_CONFIG

    def send_failure_alert(
        self, site_name: str, error_message: str, retry_count: int = 0
    ):
        if not self.enabled:
            logger.debug("Email alerts disabled, skipping...")
            return

        if not self.config.get("email") or not self.config.get("password"):
            logger.warning("Email not configured, cannot send alert")
            return

        try:
            msg = MIMEMultipart()
            msg["From"] = self.config["email"]
            msg["To"] = self.config["recipient"]
            msg["Subject"] = f"Scraper Alert: {site_name} failed"

            body = f"""
SCRAPER FAILURE ALERT
=====================

Site: {site_name}
Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Error: {error_message}
Retries attempted: {retry_count}

This is an automated alert from your self-healing scraper.

Next steps:
1. Check if the site layout changed
2. Update selectors in config.py
3. Check if you're being blocked (CAPTCHA/IP ban)
4. Review logs for more details

--
Self-Healing Scraper Alert System
            """.strip()

            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(
                self.config["smtp_server"], self.config["smtp_port"]
            ) as server:
                server.starttls()
                server.login(self.config["email"], self.config["password"])
                server.send_message(msg)

            logger.info(f"Alert email sent for {site_name} failure")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
