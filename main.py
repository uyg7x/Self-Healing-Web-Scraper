import argparse
import asyncio
import csv
import io
import logging
import subprocess
import sys
import warnings
from collections import Counter
from datetime import datetime
from pathlib import Path

if sys.platform.startswith("win"):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

warnings.filterwarnings("ignore", category=ResourceWarning)
sys.unraisablehook = lambda exc: None

from core.config import (
    AI_BACKENDS_AVAILABLE,
    COE_AI_CONFIG,
    CURRENCY_TO_INR,
    DATA_DIR,
    DELAY_CONFIG,
    GEMINI_API_KEY,
    LOG_FILE,
    PROXY_LIST,
    SITES_CONFIG,
)
from core.database import Database
from core.validators import DataValidator
from core.antiban_engine import AntiBanEngine
from core.scraper_engine import ScraperEngine

from ai.llm_healer import LLMHealer
from ai.qwen_fallback import QwenFallback
from ai.self_healing import SelfHealingSystem

from utils.human_delay import HumanDelay
from utils.pagination import crawl_site
from utils.profile_manager import has_profile, is_stale, age_label
from utils.spinner import Spinner
from utils.alerts import AlertSystem

CYAN, GREEN, YELLOW, RED, MAGENTA, RESET, BOLD = (
    "\033[96m", "\033[92m", "\033[93m", "\033[91m",
    "\033[95m", "\033[0m", "\033[1m",
)

STRATEGY_LABELS = {
    "json_ld": "JSON-LD",
    "embedded_json": "Embedded JSON",
    "css_selector": "CSS selector",
    "regex": "Regex fallback",
    "self_healing": "Self-healing",
    "llm": "Gemini AI",
    "qwen_ai_fallback": "Qwen AI",
}

def setup_logging():
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ],
    )
    for noisy in ("scraper_engine", "urllib3", "curl_cffi", "patchright", "camoufox"):
        logging.getLogger(noisy).setLevel(logging.ERROR)

def _make_delay() -> HumanDelay:
    cfg = DELAY_CONFIG.get("page_turn", {"base": 3, "sigma": 1, "hard_min": 2, "hard_max": 5, "long_pause_chance": 0.1, "long_pause_range": (15, 30)})
    return HumanDelay(
        base=cfg["base"],
        sigma=cfg["sigma"],
        hard_min=cfg["hard_min"],
        hard_max=cfg["hard_max"],
        long_pause_chance=cfg["long_pause_chance"],
        long_pause_range=cfg["long_pause_range"],
    )

def check_profile_freshness(selected_keys: list[str]) -> bool:
    browser_keys = [k for k in selected_keys if SITES_CONFIG[k].get("crawl_mode") == "browser"]
    if not browser_keys:
        return True

    stale, fresh = [], []
    for k in browser_keys:
        if not has_profile(k):
            stale.append((k, "never warmed"))
        elif is_stale(k, max_hours=24):
            stale.append((k, age_label(k)))
        else:
            fresh.append((k, age_label(k)))

    if fresh:
        print(f"\n{BOLD}Profile status:{RESET}")
        for k, age in fresh:
            print(f"  {GREEN}✓{RESET} {SITES_CONFIG[k]['name']:<22} ({age})")

    if not stale:
        print(f"\n{GREEN}All profiles are fresh. Ready to scrape.{RESET}")
        return True

    print(f"\n{YELLOW}{'=' * 62}{RESET}")
    print(f"{YELLOW}  STALE PROFILES DETECTED{RESET}")
    print(f"{YELLOW}{'=' * 62}{RESET}")
    print(f"{BOLD}These sites may return CAPTCHAs or 0 products:{RESET}\n")
    for k, age in stale:
        print(f"  {RED}✗{RESET} {SITES_CONFIG[k]['name']:<22} ({age})")

    print(f"\n{YELLOW}Fresh cookies every ~24h keeps the scraper running smoothly.{RESET}")
    print(f"\n{BOLD}Options:{RESET}")
    print(f"  {CYAN}1.{RESET} Warm stale profiles now (recommended)")
    print(f"  {CYAN}2.{RESET} Continue anyway (may get CAPTCHAs)")
    print(f"  {CYAN}3.{RESET} Cancel run")

    while True:
        choice = input(f"\n{YELLOW}Pick [1-3]: {RESET}").strip()
        if choice == "1":
            stale_keys = [k for k, _ in stale]
            print(f"\nLaunching refresh for {len(stale_keys)} site(s)...\n")
            result = subprocess.run([sys.executable, "tools/refresh_all.py", *stale_keys], cwd=str(Path(__file__).resolve().parent))
            if result.returncode != 0:
                print(f"{YELLOW}Refresh exited with code {result.returncode}.{RESET}")
            still_stale = [k for k in stale_keys if not has_profile(k) or is_stale(k)]
            if still_stale:
                names = [SITES_CONFIG[k]["name"] for k in still_stale]
                print(f"\n{YELLOW}Still stale after refresh: {names}{RESET}")
                ans = input(f"{BOLD}Continue anyway? [y/N]: {RESET}").strip().lower()
                return ans == "y"
            return True
        if choice == "2":
            print(f"{YELLOW}Continuing with stale profiles.{RESET}")
            return True
        if choice == "3":
            return False
        print(f"{RED}Invalid choice. Enter 1, 2, or 3.{RESET}")

def choose_sites() -> list[str]:
    all_keys = list(SITES_CONFIG.keys())
    print(f"\n{BOLD}Available sites:{RESET}")
    for i, key in enumerate(all_keys, 1):
        cfg = SITES_CONFIG[key]
        mode = cfg.get("crawl_mode", "url")
        age = age_label(key) if mode == "browser" else "-"
        print(f"  {CYAN}{i}.{RESET} {cfg['name']:<25} ({mode}, {age})")

    raw = input(f"\n{YELLOW}Run which sites? [comma-separated numbers, 'all', or Enter for all]: {RESET}").strip().lower()
    if not raw or raw == "all":
        return all_keys

    selected = []
    for token in raw.replace(" ", "").split(","):
        try:
            idx = int(token) - 1
            if 0 <= idx < len(all_keys):
                selected.append(all_keys[idx])
        except ValueError:
            continue
    return selected or all_keys

def ask_ai_backends() -> set[str]:
    gemini_ok = AI_BACKENDS_AVAILABLE.get("gemini", False) and bool(GEMINI_API_KEY)
    qwen_ok = AI_BACKENDS_AVAILABLE.get("qwen", False) and COE_AI_CONFIG.get("enabled", False) and bool(COE_AI_CONFIG.get("api_key", ""))

    print(f"\n{BOLD}AI fallback options:{RESET}")
    print(f"  {CYAN}1.{RESET} Gemini only  " + (f"{GREEN}[available]{RESET}" if gemini_ok else f"{RED}[no key]{RESET}"))
    print(f"  {CYAN}2.{RESET} Qwen only    " + (f"{GREEN}[available]{RESET}" if qwen_ok else f"{RED}[not configured]{RESET}"))
    print(f"  {CYAN}3.{RESET} Both")
    print(f"  {CYAN}4.{RESET} No AI (fastest)")

    while True:
        choice = input(f"\n{YELLOW}Pick [1-4, default 4]: {RESET}").strip() or "4"
        if choice == "1" and gemini_ok: return {"gemini"}
        if choice == "2" and qwen_ok: return {"qwen"}
        if choice == "3":
            picked = set()
            if gemini_ok: picked.add("gemini")
            if qwen_ok: picked.add("qwen")
            if picked: return picked
        if choice == "4": return set()
        print(f"{RED}Invalid. Enter 1-4.{RESET}")

def _print_ai_banner(ai_backends: set[str]) -> None:
    if not ai_backends:
        print(f"{YELLOW}AI fallbacks disabled.{RESET}")
    else:
        labels = [STRATEGY_LABELS.get(m, m) for m in {"gemini": "llm", "qwen": "qwen_ai_fallback"} if m in ai_backends]
        print(f"{GREEN}AI fallbacks enabled: {', '.join(labels)}.{RESET}")

async def run_interactive_search():
    print(f"\n{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{MAGENTA}                                  PJY |  Tea Scraper{RESET}")
    print(f"{CYAN}{'=' * 65}{RESET}")

    search_term = input(f"{YELLOW}Enter the product : {RESET}").strip()
    if not search_term:
        print(f"{RED}No product entered. Exiting.{RESET}")
        return

    max_pages_input = input(f"{YELLOW}Max pages per site [default 30]: {RESET}").strip()
    try:
        max_pages = int(max_pages_input) if max_pages_input else 30
    except ValueError:
        max_pages = 30

    selected_keys = choose_sites()
    if not selected_keys:
        print(f"{RED}No sites selected. Exiting.{RESET}")
        return

    if not check_profile_freshness(selected_keys):
        print(f"\n{YELLOW}Run cancelled. Refresh profiles and try again.{RESET}")
        return

    ai_backends = ask_ai_backends()
    _print_ai_banner(ai_backends)

    names = ", ".join(SITES_CONFIG[k]["name"] for k in selected_keys)
    print(f"\n{BOLD}Searching '{search_term}' - up to {max_pages} pages/site.{RESET}")
    print(f"{BOLD}Targets:{RESET} {names}\n")

    engine = ScraperEngine(ai_backends=ai_backends)
    antiban = AntiBanEngine(proxy_list=PROXY_LIST)
    healing = SelfHealingSystem()
    validator = DataValidator()
    db = Database()
    alerts = AlertSystem()
    delay = _make_delay()

    qwen = None
    if "qwen" in ai_backends:
        qwen = QwenFallback()
        if not qwen.enabled:
            print(f"{YELLOW}Qwen init failed - skipping.{RESET}")
            qwen = None

    now = datetime.now()
    search_date = now.strftime("%Y-%m-%d")
    search_time = now.strftime("%H:%M:%S")

    all_data = []
    sites_to_run = sorted([(k, SITES_CONFIG[k]) for k in selected_keys], key=lambda x: x[1]["name"])

    for idx, (site_key, cfg) in enumerate(sites_to_run, 1):
        print(f"\n{CYAN}[{idx}/{len(sites_to_run)}] {cfg['name']}{RESET}")
        try:
            raw_products = await crawl_site(
                site_key=site_key, site_config=cfg, query=search_term,
                engine=engine, antiban=antiban, healing=healing,
                validator=validator, delay=delay, max_pages=max_pages, qwen=qwen,
            )
        except Exception as e:
            print(f"  {RED} {cfg['name']}: crawl error - {e}{RESET}")
            alerts.send_failure_alert(cfg["name"], str(e))
            continue

        if not raw_products:
            print(f"  {YELLOW} {cfg['name']}: 0 products.{RESET}")
            continue

        val_msg = f"{cfg['name']} - scoring {len(raw_products)} items"
        async with Spinner(f"{val_msg}...", color="\033[96m") as s:
            valid = validator.filter_products(raw_products, search_term)
            if valid:
                s.finish(f"{val_msg} - {len(valid)} accepted")
            else:
                s.finish(f"{val_msg} - 0 survived", ok=False)

        if not valid:
            continue

        rate = CURRENCY_TO_INR.get(cfg.get("currency", "INR"), 1.0)
        for p in valid:
            p["website"] = cfg["name"]
            p["source"] = f"{cfg['name']} {STRATEGY_LABELS.get(p.get('method', ''), p.get('method', ''))}"
            p["date"] = search_date
            p["time"] = search_time

            if p.get("price_float"):
                converted = p["price_float"] * rate
                p["price_inr"] = "N/A (Price Error)" if converted > 50_000_000 else f"{converted:,.0f}"
            else:
                p["price_inr"] = "N/A"

        all_data.extend(valid)
        db.save_products(valid, site_key, {"method": "mixed", "strategy_index": 0})

        print(f"  {GREEN} {cfg['name']}: {len(valid)} valid (from {len(raw_products)} raw){RESET}")

        if cfg.get("crawl_mode") == "browser":
            await delay.between_sites()
        else:
            await delay.micro_pause()

    if not all_data:
        print(f"\n{RED} NO DATA COLLECTED.{RESET}")
        db.close()
        return

    all_data.sort(key=lambda x: (x["website"], x.get("price_float") or 0))

    safe = "".join(c for c in search_term if c.isalnum() or c == " ").rstrip()
    csv_path = DATA_DIR / (f"price_comparison_{safe.replace(' ', '_')[:30]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

    fields = ["Source", "Website Name", "Product Name", "Price (INR)", "Relevance Score", "Specifications", "Product Image URL", "Product Link", "Date", "Time"]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in all_data:
            w.writerow({
                "Source": row.get("source", ""), "Website Name": row.get("website", ""),
                "Product Name": row.get("name", ""), "Price (INR)": row.get("price_inr", ""),
                "Relevance Score": row.get("_relevance_score", "N/A"), "Specifications": row.get("specs", ""),
                "Product Image URL": row.get("image_url", "") or "", "Product Link": row.get("link", ""),
                "Date": row.get("date", ""), "Time": row.get("time", ""),
            })

    print(f"\n{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}Summary by site:{RESET}")
    counts = Counter(row["website"] for row in all_data)
    for name, cnt in counts.most_common():
        print(f"  {GREEN}{name}: {cnt} products{RESET}")

    print(f"\n{GREEN}{BOLD} Saved {len(all_data)} unique products.{RESET}")
    print(f"{GREEN} {csv_path}{RESET}")
    print(f"{CYAN}{'=' * 65}{RESET}")
    db.close()

def main():
    parser = argparse.ArgumentParser(description="Phase-6.0 self-healing comparator")
    parser.parse_args()
    setup_logging()
    try:
        asyncio.run(run_interactive_search())
    except KeyboardInterrupt:
        print(f"\n{RED}Cancelled.{RESET}")

if __name__ == "__main__":
    main()
