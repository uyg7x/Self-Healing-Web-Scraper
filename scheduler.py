"""
SCHEDULER
Runs the scraper daily at a specified time.
"""

import time
import logging
from datetime import datetime
import schedule

from config import SCHEDULE_TIME

logger = logging.getLogger(__name__)


class ScraperScheduler:
    """
    Schedules the scraper to run daily.
    """
    
    def __init__(self, scrape_function):
        """
        Initialize scheduler.
        
        Args:
            scrape_function: Function to call when schedule triggers
        """
        self.scrape_function = scrape_function
        self.running = False
    
    def start(self):
        """Start the scheduler (runs forever)."""
        logger.info(f"Scheduler started - will run daily at {SCHEDULE_TIME}")
        
        # Schedule the job
        schedule.every().day.at(SCHEDULE_TIME).do(self._run_job)
        
        self.running = True
        
        # Keep the scheduler running
        try:
            while self.running:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            self.running = False
    
    def _run_job(self):
        """Execute the scheduled scrape."""
        logger.info("=" * 60)
        logger.info(f"Scheduled scrape started at {datetime.now()}")
        logger.info("=" * 60)
        
        try:
            self.scrape_function()
            logger.info("Scheduled scrape completed successfully")
        except Exception as e:
            logger.error(f"Scheduled scrape failed: {e}", exc_info=True)
    
    def stop(self):
        """Stop the scheduler."""
        self.running = False
        logger.info("Scheduler stopped")
    
    def run_now(self):
        """Run the scrape immediately (for testing)."""
        logger.info("Running scrape immediately...")
        self._run_job()