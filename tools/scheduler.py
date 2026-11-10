import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
import time
from datetime import datetime

import schedule

from core.config import SCHEDULE_TIME

logger = logging.getLogger(__name__)


class ScraperScheduler:

    def __init__(self, scrape_function):
        self.scrape_function = scrape_function
        self.running = False

    def start(self):
        logger.info(f"Scheduler started - will run daily at {SCHEDULE_TIME}")

        schedule.every().day.at(SCHEDULE_TIME).do(self._run_job)

        self.running = True

        try:
            while self.running:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            self.running = False

    def _run_job(self):
        logger.info("=" * 60)
        logger.info(f"Scheduled scrape started at {datetime.now()}")
        logger.info("=" * 60)

        try:
            self.scrape_function()
            logger.info("Scheduled scrape completed successfully")
        except Exception as e:
            logger.error(f"Scheduled scrape failed: {e}", exc_info=True)

    def stop(self):
        self.running = False
        logger.info("Scheduler stopped")

    def run_now(self):
        logger.info("Running scrape immediately...")
        self._run_job()
