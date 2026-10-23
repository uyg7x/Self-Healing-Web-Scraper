"""
ANTI-BAN ENGINE
Phase 3: Added proxyspin health tracking & ban management.
"""

import asyncio
import random
from urllib.parse import urlparse

from curl_cffi.requests import AsyncSession as AsyncCFSession
from playwright.async_api import async_playwright

from proxy_manager import ProxyManager
from session_manager import WarmSessionManager
from stealth_fetcher import StealthBrowserFetcher


class AntiBanEngine:
    def __init__(self, proxy_list: list):
        # ProxyManager now uses proxyspin internally
        self.proxy_manager = ProxyManager(proxy_list)
        self.session_cache: dict[str, dict] = {}
        self.active_proxy: str | None = None
        self.browser = None
        self.context = None
        self.playwright = None

    # ------------------------------------------------------------------
    # Proxy helpers
    # ------------------------------------------------------------------
    def _get_fresh_proxy(self) -> str | None:
        proxy = self.proxy_manager.get()
        self.active_proxy = proxy
        return proxy

    def _blacklist_current_proxy(self):
        """Tell proxyspin this proxy failed so it benches it."""
        if self.active_proxy:
            self.proxy_manager.mark_failed(self.active_proxy)
            self.active_proxy = None

    def _mark_proxy_ok(self):
        """Tell proxyspin this proxy succeeded so it resets its health."""
        if self.active_proxy:
            self.proxy_manager.mark_ok(self.active_proxy)

    def _build_proxy_dict(self) -> dict[str, str] | None:
        """Convert self.active_proxy URL string into Playwright-style proxy dict."""
        if not self.active_proxy:
            return None
        p = urlparse(self.active_proxy)
        return {
            "server": f"http://{p.hostname}:{p.port}",
            "username": p.username or "",
            "password": p.password or "",
        }

    # ------------------------------------------------------------------
    # TLS client (fast path)
    # ------------------------------------------------------------------
    def _get_tls_client(self) -> dict:
        impersonate_list = ["chrome120", "chrome110", "chrome101"]
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
        }
        client = AsyncCFSession(
            impersonate=random.choice(impersonate_list),
            headers=headers,
            proxies={"https": self.active_proxy} if self.active_proxy else None,
            timeout=30,
            verify=False,
        )
        return {"client": client, "profile": "chrome"}

    # ------------------------------------------------------------------
    # Legacy Playwright helpers (kept as fallback)
    # ------------------------------------------------------------------
    async def _close_browser(self):
        if self.context:
            await self.context.close()
            self.context = None
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    # ------------------------------------------------------------------
    # Stealth path (CDP + Camoufox)
    # ------------------------------------------------------------------
    async def _fetch_with_stealth_browser(self, url: str) -> dict | None:
        """
        Uses CDP if a real Chrome browser is running on port 9222.
        Otherwise, falls back to Camoufox.
        """
        # 1. Try connecting to a REAL Chrome browser first (CDP Idea)
        try:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp("http://localhost:9222")
                context = browser.contexts[0]
                page = await context.new_page()

                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
                html = await page.content()
                await page.close()

                print(f"[CDP] Successfully fetched {len(html)} chars from {url}")
                return {
                    "success": True,
                    "html": html,
                    "status": 200,
                    "proxy_used": "Real Chrome (CDP)",
                    "error": None,
                }
        except Exception:
            # If Chrome isn't open, fall back to Camoufox
            pass

        # 2. Fallback to Camoufox
        proxy_dict = self._build_proxy_dict()
        domain = urlparse(url).netloc.replace("www.", "").split(".")[0]
        session_mgr = WarmSessionManager(domain, proxy=proxy_dict)
        cookies = await session_mgr.get_cookies()

        fetcher = StealthBrowserFetcher(proxy=proxy_dict, os="windows", headless=True)
        html = await fetcher.fetch(url, cookies=cookies)

        if not html:
            return None

        # Mark proxy as OK since Camoufox succeeded
        self._mark_proxy_ok()
        return {
            "success": True,
            "html": html,
            "status": 200,
            "proxy_used": self.active_proxy,
            "error": None,
        }

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------
    async def fetch(
        self, url: str, use_browser: bool = False, max_retries: int = 3
    ) -> dict | None:
        for attempt in range(max_retries):
            client = None
            try:
                # Rotate proxy before every attempt
                if not self.active_proxy or attempt > 0:
                    self._blacklist_current_proxy()
                    self._get_fresh_proxy()

                if use_browser:
                    result = await self._fetch_with_stealth_browser(url)
                    if result and result.get("success"):
                        return result

                    print(
                        f"[!] Stealth fetch attempt {attempt + 1} returned no HTML. Retrying..."
                    )
                    await asyncio.sleep(random.uniform(2.0, 5.0))
                    continue

                else:
                    client_data = self._get_tls_client()
                    client = client_data["client"]
                    resp = await client.get(url)
                    await client.close()
                    client = None

                    if resp.status_code in (403, 429, 503):
                        print(
                            f"[!] TLS fetch got {resp.status_code}. Rotating proxy and retrying..."
                        )
                        continue

                    # Mark proxy as OK since TLS fetch succeeded
                    self._mark_proxy_ok()
                    return {
                        "success": True,
                        "html": resp.text,
                        "status": resp.status_code,
                        "proxy_used": self.active_proxy,
                        "error": None,
                    }

            except Exception as e:
                print(f"[!] Fetch attempt {attempt + 1} failed: {e!s}")
                if client is not None:
                    try:
                        await client.close()
                    except Exception:
                        pass
                await self._close_browser()
                continue

        return {
            "success": False,
            "html": None,
            "status": None,
            "proxy_used": self.active_proxy,
            "error": "Max retries exceeded",
        }
