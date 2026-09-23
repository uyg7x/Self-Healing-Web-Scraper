import asyncio
import random
from playwright.async_api import async_playwright
import playwright_stealth as stealth

async def fetch_with_stealth(url: str):
    async with async_playwright() as p:
        # Launch with evasion args
        browser = await p.chromium.launch(
            headless=False,  # Set to True in production
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--disable-extensions",
                "--disable-plugins-except=Chrome PDF Viewer",
                "--disable-plugins",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-client-side-phishing-detection",
                "--disable-default-apps",
                "--disable-hang-monitor",
                "--disable-popup-blocking",
                "--disable-prompt-on-repost",
                "--disable-sync",
                "--metrics-recording-only",
                "--no-first-run",
                "--safebrowsing-disable-auto-update",
                "--disable-features=TranslateUI",
                "--disable-ipc-flooding-protection",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--mute-audio",
                "--no-default-browser-check",
                "--no-pings",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            java_script_enabled=True,
            ignore_https_errors=True,
            bypass_csp=True,
        )

        # Apply stealth techniques
        await stealth.apply_stealth(context)

        # Remove navigator.webdriver flag
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
            });
        """)

        # Simulate real user behavior
        await context.add_init_script("""
            window.chrome = { runtime: {}, loadTimes: () => {}, csi: () => {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'permissions', {
                get: () => ({
                    query: () => Promise.resolve({ state: 'granted' })
                })
            });
        """)

        page = await context.new_page()

        # Human-like delay before navigation
        await page.wait_for_timeout(random.randint(1500, 3500))

        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            html = await page.content()
            status = 200
        except Exception as e:
            print(f"[!] Navigation failed: {e}")
            html = None
            status = 0

        await browser.close()
        return {"html": html, "status": status}

