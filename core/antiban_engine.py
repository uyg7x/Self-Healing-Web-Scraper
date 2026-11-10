import asyncio
import logging
import random
from urllib.parse import urlparse
from curl_cffi.requests import AsyncSession as AsyncCFSession
from utils.profile_manager import has_profile, profile_path
from .proxy_manager import ProxyManager

logger = logging.getLogger(__name__)


SITE_KEY_FOR_HOST = {
    "amazon.in": "amazon",
    "amazon.com": "amazon",
    "flipkart.com": "flipkart",
    "meesho.com": "meesho",
    "alibaba.com": "alibaba",
    "robu.in": "robu",
}


def _site_key_for_url(url: str) -> str | None:
    host = urlparse(url).netloc.lower().replace("www.", "")
    for domain, key in SITE_KEY_FOR_HOST.items():
        if host == domain or host.endswith("." + domain):
            return key
    return None


class AntiBanEngine:
    IMPERSONATE_LIST = ["chrome120", "chrome124"]

    def __init__(self, proxy_list: list):
        self.proxy_manager = ProxyManager(proxy_list)
        self.active_proxy: str | None = None
        self._engine_memory: dict[str, str] = {}


    def _get_fresh_proxy(self):
        self.active_proxy = self.proxy_manager.get()
        return self.active_proxy

    def _blacklist_current_proxy(self):
        if self.active_proxy:
            self.proxy_manager.mark_failed(self.active_proxy)
            self.active_proxy = None

    def _mark_proxy_ok(self):
        if self.active_proxy:
            self.proxy_manager.mark_ok(self.active_proxy)


    async def _fetch_tls(self, url: str):
        proxy = self._get_fresh_proxy()
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            async with AsyncCFSession(
                impersonate=random.choice(self.IMPERSONATE_LIST),
                headers=headers,
                proxies={"https": proxy, "http": proxy} if proxy else None,
                timeout=30,
                verify=False,
            ) as client:
                resp = await client.get(url)
                if resp.status_code in (403, 429, 503):
                    self._blacklist_current_proxy()
                    return None
                if resp.status_code >= 400:
                    return None
                self._mark_proxy_ok()
                return resp.text
        except Exception as e:
            logger.debug(f"[TLS] {url} -> {e}")
            self._blacklist_current_proxy()
            return None


    async def _fetch_patchright(self, url: str, humanize: bool = True):
        try:
            from patchright.async_api import async_playwright
        except ImportError:
            return None

        proxy = self._get_fresh_proxy()
        proxy_arg = None
        if proxy:
            p = urlparse(proxy)
            proxy_arg = {
                "server": f"http://{p.hostname}:{p.port}",
                "username": p.username or "",
                "password": p.password or "",
            }

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
                    proxy=proxy_arg,
                )
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    locale="en-US",
                )
                warm = await context.new_page()
                try:
                    await warm.goto("https://www.google.com", wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(random.uniform(0.6, 1.8))
                except Exception:
                    pass
                await warm.close()

                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                if humanize:
                    try:
                        await page.mouse.move(
                            random.randint(200, 800),
                            random.randint(200, 700),
                            steps=random.randint(12, 28),
                        )
                        await asyncio.sleep(random.uniform(0.3, 1.1))
                        await page.mouse.wheel(0, random.randint(200, 900))
                    except Exception:
                        pass

                await page.wait_for_timeout(random.uniform(800, 2200))
                html = await page.content()
                await browser.close()
                if html and len(html) >= 500:
                    self._mark_proxy_ok()
                    return html
                return None
        except Exception as e:
            logger.debug(f"[Patchright] {url} -> {e}")
            return None


    async def _fetch_camoufox(self, url: str):
        try:
            from camoufox.async_api import AsyncCamoufox
        except ImportError:
            return None

        site_key = _site_key_for_url(url)
        proxy = self._get_fresh_proxy()
        proxy_arg = None
        if proxy:
            p = urlparse(proxy)
            proxy_arg = {
                "server": f"http://{p.hostname}:{p.port}",
                "username": p.username or "",
                "password": p.password or "",
            }


        kwargs = {
            "headless": True,
            "os": "windows",
            "geoip": True,
            "humanize": True,
        }
        if proxy_arg:
            kwargs["proxy"] = proxy_arg

        if site_key and has_profile(site_key):
            kwargs["persistent_context"] = True
            kwargs["user_data_dir"] = str(profile_path(site_key))
            logger.info(f"[Camoufox] using saved profile for {site_key}")
        else:
            logger.info(f"[Camoufox] no profile for {site_key} - fresh context")

        try:
            async with AsyncCamoufox(**kwargs) as ctx:
        
                if kwargs.get("persistent_context"):
                    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
                else:
                    context = await ctx.new_context()
                    page = await context.new_page()

                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(random.uniform(1500, 3500))
                html = await page.content()
                if html and len(html) >= 500:
                    self._mark_proxy_ok()
                    return html
                return None
        except Exception as e:
            logger.debug(f"[Camoufox] {url} -> {e}")
            return None


    def _escalation_order(self, site_key, use_browser):
        base = ["tls"]
        if use_browser:
            base.append("patchright")
        if site_key and site_key in self._engine_memory:
            remembered = self._engine_memory[site_key]
            if remembered in base:
                base.remove(remembered)
                base.insert(0, remembered)
        if "camoufox" not in base:
            base.append("camoufox")
        return base

    async def fetch(self, url: str, site_key: str | None = None, use_browser: bool = False):
        engines = self._escalation_order(site_key, use_browser)
        for name in engines:
            if name == "tls":
                html = await self._fetch_tls(url)
            elif name == "patchright":
                html = await self._fetch_patchright(url)
            elif name == "camoufox":
                html = await self._fetch_camoufox(url)
            else:
                continue
            if html:
                if site_key:
                    self._engine_memory[site_key] = name
                return html, name
        return None, "blocked"
