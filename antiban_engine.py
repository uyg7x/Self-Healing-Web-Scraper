import asyncio
import random
import time
from typing import Dict, Optional
from urllib.parse import urlparse
from datetime import datetime, timedelta

from curl_cffi.requests import AsyncSession as AsyncCFSession
from playwright.async_api import async_playwright
from proxy_manager import ProxyManager

class AntiBanEngine:
    def __init__(self, proxy_list: list):
        self.proxy_manager = ProxyManager(proxy_list)
        self.session_cache: Dict[str, dict] = {}
        self.active_proxy: Optional[str] = None
        self.browser = None
        self.context = None
        self.playwright = None

    def _get_fresh_proxy(self) -> Optional[str]:
        proxy = self.proxy_manager.get()
        self.active_proxy = proxy
        return proxy

    def _blacklist_current_proxy(self):
        if self.active_proxy:
            self.active_proxy = None

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
            verify=False
        )
        return {"client": client, "profile": "chrome"}

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

    async def _launch_browser(self):
        self.playwright = await async_playwright().start()
        proxy = self.proxy_manager.get()
        self.active_proxy = proxy
        
        launch_args = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security"
            ]
        }
        
        if proxy:
            proxy_url = urlparse(proxy)
            launch_args["proxy"] = {
                "server": f"http://{proxy_url.hostname}:{proxy_url.port}",
                "username": proxy_url.username or "",
                "password": proxy_url.password or ""
            }
        
        self.browser = await self.playwright.chromium.launch(**launch_args)
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            ignore_https_errors=True
        )
        
        return self.context

    async def fetch(self, url: str, use_browser: bool = False) -> Optional[dict]:
        domain = urlparse(url).netloc
        max_retries = 3
        
        for attempt in range(max_retries):
            client = None
            try:
                if not self.active_proxy or attempt > 0:
                    self._blacklist_current_proxy()
                    self._get_fresh_proxy()

                if use_browser:
                    context = await self._launch_browser()
                    page = await context.new_page()
                    
                    try:
                        from playwright_stealth import stealth_async
                        await stealth_async(page)
                    except Exception:
                        pass

                    await page.wait_for_timeout(random.randint(800, 2200))
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    status = response.status if response else 0
                    
                    if status in [403, 429, 503]:
                        await self._close_browser()
                        continue
                        
                    await page.wait_for_timeout(random.randint(1000, 3000))
                    html = await page.content()
                    await self._close_browser()
                    
                    return {
                        "success": True, 
                        "html": html, 
                        "status": status, 
                        "proxy_used": self.active_proxy, 
                        "error": None
                    }
                else:
                    client_data = self._get_tls_client()
                    client = client_data["client"]
                    resp = await client.get(url)
                    
                    if resp.status_code in [403, 429, 503]:
                        await client.close()
                        continue
                    
                    await client.close()
                    return {
                        "success": True, 
                        "html": resp.text, 
                        "status": resp.status_code, 
                        "proxy_used": self.active_proxy, 
                        "error": None
                    }
                    
            except Exception as e:
                print(f"[!] Fetch attempt {attempt+1} failed: {str(e)}")
                if client is not None: 
                    await client.close()
                await self._close_browser()
                continue
                
        return {
            "success": False, 
            "html": None, 
            "status": None, 
            "proxy_used": self.active_proxy, 
            "error": "Max retries exceeded"
        }