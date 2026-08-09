"""
SELF-HEALING SYSTEM
This module tracks which selectors work and promotes successful ones.
When a site changes its layout, the scraper learns which new selector works
and remembers it for next time.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from config import SELECTOR_HISTORY_PATH

logger = logging.getLogger(__name__)


class SelfHealingSystem:
    """
    The self-healing brain of the scraper.
    
    Think of it as the robot's "memory" - it remembers what worked before
    and tries that first next time.
    """
    
    def __init__(self):
        """Load or create the selector history database."""
        self.history_path = Path(SELECTOR_HISTORY_PATH)
        self.history = self._load_history()
    
    def _load_history(self) -> Dict:
        """Load selector history from JSON file."""
        if self.history_path.exists():
            try:
                with open(self.history_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load history: {e}")
        
        return {}
    
    def _save_history(self):
        """Save selector history to JSON file."""
        try:
            with open(self.history_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2)
            logger.debug("Saved selector history")
        except IOError as e:
            logger.error(f"Failed to save history: {e}")
    
    def get_prioritized_selectors(
        self,
        site_name: str,
        selectors: List[Dict]
    ) -> List[Dict]:
        """
        Reorder selectors based on past success.
        
        If we previously found that selector #2 worked, try it first this time.
        
        Args:
            site_name: Name of the site (e.g., "amazon")
            selectors: List of selector dictionaries
        
        Returns:
            Reordered list of selectors (best first)
        """
        site_history = self.history.get(site_name, {})
        
        # Get the best selector index from history
        best_index = site_history.get("best_selector", 0)
        success_count = site_history.get("success_count", {})
        
        if best_index >= len(selectors):
            logger.warning(f"Best selector index {best_index} out of range")
            return selectors
        
        # If this selector has worked before, move it to front
        if best_index > 0:
            logger.info(f"Promoting selector #{best_index + 1} to front (worked previously)")
            reordered = [selectors[best_index]]
            reordered.extend([s for i, s in enumerate(selectors) if i != best_index])
            return reordered
        
        # Log success counts
        if success_count:
            logger.info(f"Previous success counts: {success_count}")
        
        return selectors
    
    def record_success(self, site_name: str, strategy_index: int, method: str):
        """
        Record that a selector strategy worked.

        This promotes it to be tried first next time.

        Args:
            site_name: Name of the site
            strategy_index: Index of the working selector (0-based)
            method: "css_selector", "regex", "json_ld", or "self_healing"
        """
        if site_name not in self.history:
            self.history[site_name] = {
                "best_selector": 0,
                "success_count": {},
                "last_success": None,
                "method": None,
            }

        site_history = self.history[site_name]

        # Update success count
        if "success_count" not in site_history:
            site_history["success_count"] = {}

        key = f"{method}_{strategy_index}"
        site_history["success_count"][key] = site_history["success_count"].get(key, 0) + 1

        # Prefer JSON-LD when available - it's the most resilient
        if method == "json_ld":
            site_history["method"] = "json_ld"
            logger.info(f"🏷️ JSON-LD extraction works for {site_name} - will be tried first next time")
        elif method == "css_selector":
            current_best = site_history.get("best_selector", 0)
            current_best_count = site_history["success_count"].get(f"css_selector_{current_best}", 0)
            new_count = site_history["success_count"][key]
            if new_count > current_best_count:
                logger.info(f"Promoting selector #{strategy_index + 1} as new best for {site_name}")
                site_history["best_selector"] = strategy_index

        # Update last success time
        from datetime import datetime
        site_history["last_success"] = datetime.now().isoformat()
        site_history["method"] = method

        self._save_history()
        logger.info(f"Recorded success for {site_name}: strategy {strategy_index}, method {method}")
    
    def record_failure(self, site_name: str, error: str):
        """
        Record that scraping failed for a site.
        
        Args:
            site_name: Name of the site
            error: Error message
        """
        if site_name not in self.history:
            self.history[site_name] = {}
        
        if "failures" not in self.history[site_name]:
            self.history[site_name]["failures"] = []
        
        self.history[site_name]["failures"].append({
            "timestamp": self._now(),
            "error": error,
        })
        
        # Keep only last 10 failures
        self.history[site_name]["failures"] = self.history[site_name]["failures"][-10:]
        
        self._save_history()
        logger.info(f"Recorded failure for {site_name}: {error}")
    
    def get_site_health(self, site_name: str) -> Dict:
        """
        Get health statistics for a site.
        
        Returns:
            Dictionary with success/failure counts and last activity
        """
        site_history = self.history.get(site_name, {})
        
        success_count = sum(
            count for key, count in site_history.get("success_count", {}).items()
            if key.startswith("css_selector_")
        )
        failure_count = len(site_history.get("failures", []))
        
        return {
            "site": site_name,
            "successes": success_count,
            "failures": failure_count,
            "success_rate": success_count / (success_count + failure_count) if (success_count + failure_count) > 0 else 0,
            "best_selector": site_history.get("best_selector", 0),
            "last_success": site_history.get("last_success"),
            "last_failure": site_history["failures"][-1]["timestamp"] if site_history.get("failures") else None,
        }
    
    def _now(self) -> str:
        """Get current timestamp."""
        from datetime import datetime
        return datetime.now().isoformat()