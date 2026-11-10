import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import sys
from pathlib import Path

from camoufox.async_api import AsyncCamoufox

from core.config import SITES_CONFIG
from utils.profile_manager import has_profile, profile_path


async def main(site_key: str, query: str):
    cfg = SITES_CONFIG[site_key]
    url = cfg["base_search_url"].replace("{query}", query.replace(" ", "+"))

    print(f"\n=== {cfg['name']} — {url} ===\n")

    kwargs = {"headless": True, "os": "windows", "geoip": True, "humanize": True}
    if has_profile(site_key):
        kwargs["persistent_context"] = True
        kwargs["user_data_dir"] = str(profile_path(site_key))

    async with AsyncCamoufox(**kwargs) as ctx:
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2500)

        html = await page.content()
        size_kb = len(html) // 1024
        print(f"Page size: {size_kb} KB")
        print(f"Title: {await page.title()}\n")

    
        challenge = [m for m in (
            "punish-component", "awsc.js", "baxia-punish",
            "cf-chl", "captcha-delivery", "please verify you are a human",
        ) if m in html]
        if challenge:
            print(f"⚠ CHALLENGE MARKERS FOUND: {challenge}")

       
        diagnostics = {
            "alibaba": [
                "div[data-spm='normal_offer']",
                ".search-card-item",
                "h2.search-card-e-title",
                "window.__page__data" in html and "window.__page__data found" or None,
            ],
            "newegg": [
                ".item-cell",
                ".item-container",
                ".item-title",
                ".price-current",
                "li[class*='item']",
            ],
            "ebay": [
                "li.s-card",
                "li.s-item",
                ".srp-results li",
                ".s-card__title",
            ],
            "temu": [
                "div[data-uniqid]",
                "div[class*='product-card']",
                "a[href*='goods.html']",
                "[class*='title']",
            ],
            "robu": [
                ".woocommerce-loop-product__title",
                ".product-title",
                "li.product",
                ".price .amount",
            ],
        }

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        print("Selector matches:")
        for sel in diagnostics.get(site_key, []):
            if sel and "window." in str(sel):
                print(f"  ✓ {sel}")
            elif sel:
                count = len(soup.select(sel))
                mark = "✓" if count else "✗"
                print(f"  {mark} {sel}  →  {count}")

       
        out = Path(f"data/diag_{site_key}.html")
        out.parent.mkdir(exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"\nSaved → {out} ({size_kb} KB)")
        print("Open in a browser or text editor to inspect.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python diagnose_site.py <site_key> <query>")
        sys.exit(1)
    try:
        asyncio.run(main(sys.argv[1].lower(), sys.argv[2]))
    except KeyboardInterrupt:
        pass