import json
import logging
from pathlib import Path

from camoufox.async_api import AsyncCamoufox

logger = logging.getLogger(__name__)

SESSION_DIR = Path("data/sessions")
SESSION_DIR.mkdir(parents=True, exist_ok=True)


class WarmSessionManager:
    def __init__(self, site_key: str, proxy: dict[str, str] | None = None):
        self.site_key = site_key
        self.proxy = proxy
        self.session_path = SESSION_DIR / f"{site_key}_cookies.json"

    async def get_cookies(self) -> list | None:
        if not self.session_path.exists():
            return None
        try:
            return json.loads(self.session_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load session for {self.site_key}: {e}")
            return None

    async def save_cookies(self, cookies: list) -> None:
        self.session_path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")

    async def warm_up(self, login_url: str, headless: bool = False) -> bool:
        try:
            async with AsyncCamoufox(
                headless=headless, os="windows", geoip=True, proxy=self.proxy
            ) as browser:
                page = await browser.new_page()
                await page.goto(login_url)
                input("Press Enter after logging in >>> ")
                await self.save_cookies(await page.context.cookies())
                return True
        except Exception as e:
            logger.error(f"Warm-up failed: {e}")
            return False
