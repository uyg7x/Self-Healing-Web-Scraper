"""
EMAIL ALERTS
Sends email alerts when scraping fails.
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from config import EMAIL_CONFIG

logger = logging.getLogger(__name__)


class AlertSystem:
    """
    Sends email alerts for scraping failures.
    """
    
    def __init__(self):
        """Initialize alert system."""
        self.enabled = EMAIL_CONFIG.get("enabled", False)
        self.config = EMAIL_CONFIG
    
    def send_failure_alert(
        self,
        site_name: str,
        error_message: str,
        retry_count: int = 0
    ):
        """
        Send email alert about scraping failure.
        
        Args:
            site_name: Name of the site that failed
            error_message: Error description
            retry_count: Number of retries attempted
        """
        if not self.enabled:
            logger.debug("Email alerts disabled, skipping...")
            return
        
        if not self.config.get("email") or not self.config.get("password"):
            logger.warning("Email not configured, cannot send alert")
            return
        
        try:
            # Create email message
            msg = MIMEMultipart()
            msg["From"] = self.config["email"]
            msg["To"] = self.config["recipient"]
            msg["Subject"] = f"🚨 Scraper Alert: {site_name} failed"
            
            # Create email body
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
            
            # Send email
            with smtplib.SMTP(self.config["smtp_server"], self.config["smtp_port"]) as server:
                server.starttls()
                server.login(self.config["email"], self.config["password"])
                server.send_message(msg)
            
            logger.info(f"Alert email sent for {site_name} failure")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")