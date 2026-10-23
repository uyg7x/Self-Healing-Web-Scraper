import logging

from camoufox.async_api import AsyncCamoufox

logger = logging.getLogger(__name__)


class StealthBrowserFetcher:
    def __init__(
        self,
        proxy: dict[str, str] | None = None,
        os: str = "windows",
        headless: bool = True,
    ):
        self.proxy = proxy
        self.os = os
        self.headless = headless

    async def fetch(
        self,
        url: str,
        cookies: list | None = None,
        wait_until: str = "domcontentloaded",
        timeout: int = 30000,
    ) -> str | None:
        try:
            kwargs = {"headless": self.headless, "os": self.os, "geoip": True}
            if self.proxy:
                kwargs["proxy"] = self.proxy

            async with AsyncCamoufox(**kwargs) as browser:
                # Create a context explicitly so we can add cookies
                context = await browser.new_context()
                if cookies:
                    await context.add_cookies(cookies)
                    logger.info(f"Applied {len(cookies)} warm cookies")
                page = await context.new_page()
                await page.goto(url, wait_until=wait_until, timeout=timeout)
                return await page.content()
        except Exception as e:
            logger.error(f"[StealthFetcher] Failed to fetch {url}: {e}")
            return None
