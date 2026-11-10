

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


async def warm_one(site_key: str, ask_overwrite: bool = True) -> bool:
    if site_key not in SITES_CONFIG:
        print(f"{RED}Unknown site '{site_key}'.{RESET}")
        return False

    cfg = SITES_CONFIG[site_key]
    prof = profile_path(site_key)

    if ask_overwrite and any(prof.iterdir()):
        ans = input(
            f"{YELLOW}Profile for '{site_key}' exists ({age_label(site_key)}). "
            f"Overwrite? [y/N]: {RESET}"
        ).strip().lower()
        if ans == "y":
            clear_profile(site_key)

    print(f"\n{CYAN}{'=' * 60}{RESET}")
    print(f"{YELLOW}WARMING: {cfg['name']}{RESET}")
    print(f"{CYAN}{'=' * 60}{RESET}")
    print(LOGIN_HINTS.get(site_key, "Browse normally, then return here."))
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
            input, f"{YELLOW}Press Enter when done browsing >>> {RESET}"
        )

    mark_warmed(site_key)
    print(f"{GREEN}✓ Profile saved + marked fresh for {site_key}{RESET}\n")
    return True


async def main(targets: list[str]):
    if "all" in targets:
        targets = [
            k for k, v in SITES_CONFIG.items()
            if v.get("crawl_mode") == "browser"
        ]

    print(f"\nRefreshing {len(targets)} profile(s): {', '.join(targets)}\n")

    for i, k in enumerate(targets, 1):
        print(f"{CYAN}[{i}/{len(targets)}]{RESET} {SITES_CONFIG[k]['name']}")
        ok = await warm_one(k)
        if not ok:
            print(f"{YELLOW}⚠ Skipped {k}{RESET}")

    print(f"\n{GREEN}✓ Done.{RESET}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tools/warm_site.py <site_key|all> [site_key ...]")
        print(f"Available: {', '.join(SITES_CONFIG.keys())}")
        sys.exit(1)
    try:
        asyncio.run(main([t.lower() for t in sys.argv[1:]]))
    except KeyboardInterrupt:
        print("\nCancelled.")