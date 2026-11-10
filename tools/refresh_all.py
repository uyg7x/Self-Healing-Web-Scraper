

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio

from camoufox.async_api import AsyncCamoufox

from core.config import SITES_CONFIG
from utils.profile_manager import profile_path, clear_profile, mark_warmed, age_label

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

LOGIN_HINTS = {
    "amazon": "Log into Amazon. Solve any CAPTCHA. Land on homepage.",
    "ebay": "Browse eBay. Accept cookies. Click one product.",
    "newegg": "Browse Newegg. Accept cookies. Click one product.",
    "temu": "Browse Temu. Accept cookie banner. Click a product.",
    "flipkart": "Browse Flipkart. Accept cookies. Search once.",
    "meesho": "Browse Meesho. Accept cookies.",
    "alibaba": "Browse Alibaba. Accept cookies. Click a product.",
    "shein": "Browse Shein. Accept cookies. Scroll the homepage.",
    "robu": "Browse Robu.in. Accept cookies.",
}


async def warm_one(site_key: str) -> bool:
    cfg = SITES_CONFIG[site_key]

    print(f"\n{CYAN}{'=' * 60}{RESET}")
    print(f"{YELLOW}WARMING: {cfg['name']}{RESET}  (was: {age_label(site_key)})")
    print(f"{CYAN}{'=' * 60}{RESET}")
    print(LOGIN_HINTS.get(site_key, "Browse normally."))
    print()

    async with AsyncCamoufox(
        headless=False,
        os="windows",
        geoip=True,
        persistent_context=True,
        user_data_dir=str(profile_path(site_key)),
        humanize=True,
    ) as ctx:
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        try:
            await page.goto(cfg["url"], wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            print(f"{RED}Navigation failed: {e}{RESET}")
            return False

        await asyncio.to_thread(
            input, f"{YELLOW}Press Enter when done >>> {RESET}"
        )

    mark_warmed(site_key)
    print(f"{GREEN}✓ {site_key} refreshed{RESET}")
    return True


async def main(targets: list[str] | None, fresh: bool = False):
    if targets is None:
        targets = [
            k for k, v in SITES_CONFIG.items()
            if v.get("crawl_mode") == "browser"
        ]
    else:
        targets = [t for t in targets if t in SITES_CONFIG]

    if not targets:
        print(f"{RED}No valid targets.{RESET}")
        return

    print(f"\n{CYAN}{'=' * 60}{RESET}")
    print(f"{YELLOW}  REFRESH ALL PROFILES{RESET}")
    print(f"{CYAN}{'=' * 60}{RESET}")
    print(f"Targets: {', '.join(targets)}")
    if fresh:
        print(f"{YELLOW}--fresh: clearing old profiles first{RESET}")
    print()

    for i, k in enumerate(targets, 1):
        print(f"{CYAN}[{i}/{len(targets)}]{RESET} {SITES_CONFIG[k]['name']}")
        if fresh:
            clear_profile(k)
            print(f"  Cleared old profile for {k}")
        ok = await warm_one(k)
        if not ok:
            print(f"{YELLOW}⚠ Skipped {k}{RESET}")

    print(f"\n{GREEN}{'=' * 60}{RESET}")
    print(f"{GREEN}✓ All profiles refreshed.{RESET}")
    print(f"{GREEN}{'=' * 60}{RESET}\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    fresh = "--fresh" in args
    targets = [a for a in args if a != "--fresh"] or None

    try:
        asyncio.run(main(targets, fresh=fresh))
    except KeyboardInterrupt:
        print("\nCancelled.")