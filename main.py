"""
MAIN RUNNER (Interactive Price Comparator with Clean UI & Phase 4 Sanity Checks)
"""

import argparse
import asyncio
import csv
import io
import logging
import sys
import warnings
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

# Fix Windows Unicode crashes for emojis/colors
if sys.platform.startswith("win"):
    try:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace"
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding="utf-8", errors="replace"
        )
    except Exception:
        pass

warnings.filterwarnings("ignore", category=ResourceWarning)
sys.unraisablehook = lambda exc: None

from alerts import AlertSystem
from config import CURRENCY_TO_INR, DATA_DIR, LOG_FILE, SITES_CONFIG
from database import Database
from qwen_fallback import QwenFallback
from scraper_engine import ScraperEngine
from self_healing import SelfHealingSystem
from validators import DataValidator

# ==========================================
# 🎨 ANSI COLOR CODES
# ==========================================
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
RESET = "\033[0m"
BOLD = "\033[1m"

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
    # 🔇 We only log ERRORS to the terminal, but keep everything in the log file.
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
            logging.StreamHandler(sys.stderr),  # Terminal shows warnings/errors only
        ],
    )
    # Silence specific noisy libraries
    logging.getLogger("scraper_engine").setLevel(logging.ERROR)
    logging.getLogger("stealth_fetcher").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    return logging.getLogger(__name__)


# ==========================================
# 🎡 SPINNER ANIMATION
# ==========================================
async def show_spinner(message: str, stop_event: asyncio.Event):
    chars = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
    i = 0
    while not stop_event.is_set():
        sys.stdout.write(f"\r{CYAN}{message} {chars[i % len(chars)]}{RESET}   ")
        sys.stdout.flush()
        await asyncio.sleep(0.1)
        i += 1
    sys.stdout.write("\r" + " " * (len(message) + 10) + "\r")  # Clear line
    sys.stdout.flush()


# ==========================================
# 🕷️ SCRAPING LOGIC (PHASE 2 HYBRID CASCADE)
# ==========================================
async def scrape_site(
    site_key,
    site_config,
    engine,
    healing,
    validator,
    db,
    alerts,
    results_collector,
    search_date,
    search_time,
    search_term,
    qwen=None,
):
    logger = logging.getLogger(__name__)
    site_name = site_config["name"]
    target_url = site_config["category_url"]
    selectors = healing.get_prioritized_selectors(site_key, site_config["selectors"])

    products = []
    scrape_info = {}
    html = None

    # --- 1. FAST TLS FETCH (Phase 2) ---
    stop_spinner = asyncio.Event()
    spinner_task = asyncio.create_task(
        show_spinner(f"Scanning {BOLD}{site_name}{RESET} (Fast)...", stop_spinner)
    )

    # We pass max_retries=1 to fail fast if the site blocks standard requests
    html = await engine.fetch_page(target_url, js_required=False, max_retries=1)
    if html:
        products, scrape_info = engine.extract_data(
            html, site_config["url"], selectors, site_config["regex_fallback"]
        )

    # --- 2. HEAVY BROWSER FALLBACK (Phase 2) ---
    if not products and site_config.get("js_required", False):
        stop_spinner.set()
        await spinner_task
        print(
            f"  {YELLOW}⚠{RESET} {site_name}: Fast fetch empty. Launching Stealth Browser..."
        )

        stop_spinner = asyncio.Event()
        spinner_task = asyncio.create_task(
            show_spinner(f"Rendering {BOLD}{site_name}{RESET} (JS)...", stop_spinner)
        )

        html = await engine.fetch_page(target_url, js_required=True)
        if html:
            products, scrape_info = engine.extract_data(
                html, site_config["url"], selectors, site_config["regex_fallback"]
            )

    stop_spinner.set()
    await spinner_task

    used_method = scrape_info.get("method", "")

    # --- 3. QWEN AI FALLBACK ---
    if not products and qwen is not None and qwen.enabled and html:
        qwen_products = qwen.extract_products(
            html, search_term, target_site=site_config["url"]
        )
        if qwen_products:
            products = qwen_products
            used_method = "qwen_ai_fallback"
            scrape_info = {"strategy_index": -5, "method": "qwen_ai_fallback"}

    if not products:
        print(f"  {YELLOW}⚠{RESET} {site_name}: No products found.")
        return

    # --- 4. PYDANTIC SCHEMA VALIDATION (Phase 4) ---
    valid_products = validator.filter_products(products, search_term)
    if not valid_products:
        print(
            f"  {YELLOW}⚠{RESET} {site_name}: Found items, but they failed validation/relevance checks."
        )
        return

    # Convert price to INR
    rate = CURRENCY_TO_INR.get(site_config.get("currency", "INR"), 1.0)
    source_label = f"{site_name} • {STRATEGY_LABELS.get(used_method, used_method)}"

    for p in valid_products:
        p["website"] = site_name
        p["source"] = source_label
        p["extraction_method"] = used_method
        p["date"] = search_date
        p["time"] = search_time

        # 🔥 PHASE 4: Safe Currency Conversion
        if p.get("price_float"):
            converted_price = p["price_float"] * rate
            # Absolute failsafe: Nothing on these sites costs > 5 Crores
            if converted_price > 50000000:
                p["price_inr"] = "N/A (Price Error)"
                p["price_float"] = 0  # Invalidates it
            else:
                p["price_inr"] = f"₹{converted_price:,.0f}"
        else:
            p["price_inr"] = "N/A"

    results_collector.extend(valid_products)
    db.save_products(valid_products, site_key, scrape_info)
    healing.record_success(site_key, scrape_info.get("strategy_index", 0), used_method)

    print(
        f"  {GREEN}✓{RESET} {site_name}: Extracted {GREEN}{len(valid_products)}{RESET} valid products ({source_label})."
    )


# ==========================================
# 🎮 POST-SCRAPE MENU
# ==========================================
def handle_results_menu(scraped_data, csv_path, search_term):
    if not scraped_data:
        return

    while True:
        print(f"\n{BOLD}What would you like to do next?{RESET}")
        print(f"  {CYAN}1.{RESET} View extracted products")
        print(f"  {CYAN}2.{RESET} How to get Amazon data (Warm Cookies)")
        print(f"  {CYAN}3.{RESET} Exit")

        choice = input(f"\n{YELLOW}Enter choice [1-3]: {RESET}").strip()

        if choice == "1":
            print(f"\n{MAGENTA}--- Extracted Products for '{search_term}' ---{RESET}")
            print(f"{'Website':<15} | {'Price':<15} | {'Name'}")
            print("-" * 80)
            for row in scraped_data:
                name = (
                    row.get("name", "")[:50] + "..."
                    if len(row.get("name", "")) > 50
                    else row.get("name", "")
                )
                price_str = str(row.get("price_inr", "N/A"))
                print(f"{row.get('website'):<15} | {price_str:<15} | {name}")
            print(f"\n{GREEN}✓ Complete CSV saved at: {csv_path}{RESET}\n")

        elif choice == "2":
            print(f"\n{YELLOW}--- Amazon Warm-Up Instructions ---{RESET}")
            print("Amazon requires a 'Warm Session' to prevent bot detection.")
            print("1. Run: python warm_amazon.py")
            print("2. A browser will open. Log into Amazon normally.")
            print("3. Press Enter in this terminal once you are logged in.")
            print("4. The scraper will now automatically use these cookies.\n")

        elif choice == "3":
            print(f"\n{GREEN}Thank you for using the Self-Healing Scraper!{RESET}\n")
            break


# ==========================================
# 🚀 MAIN EXECUTION
# ==========================================
async def run_interactive_search():
    print(f"\n{CYAN}{'=' * 65}{RESET}")
    print(f"{BOLD}{MAGENTA}  SELF-HEALING E-COMMERCE PRICE COMPARATOR{RESET}")
    print(f"{CYAN}{'=' * 65}{RESET}")

    # Check for Amazon cookies
    if not Path("data/sessions/amazon_cookies.json").exists():
        print(f"{YELLOW}⚠ WARNING: Amazon cookies not found!{RESET}")
        print("  Amazon will likely block the scraper. To fix this:")
        print(
            f"  Run {BOLD}python warm_amazon.py{RESET} in a separate terminal first.\n"
        )

    search_term = input(
        f"{YELLOW}Enter the product you want to search for: {RESET}"
    ).strip()
    if not search_term:
        print(f"{RED}No product entered. Exiting.{RESET}")
        return

    print(f"\n{BOLD}Searching '{search_term}' across platforms...{RESET}\n")

    encoded_query = quote_plus(search_term)
    all_scraped_data = []

    engine = ScraperEngine()
    healing = SelfHealingSystem()
    validator = DataValidator()
    db = Database()
    alerts = AlertSystem()
    qwen = QwenFallback()

    now = datetime.now()
    search_date = now.strftime("%Y-%m-%d")
    search_time = now.strftime("%H:%M:%S")

    sorted_sites = sorted(SITES_CONFIG.items(), key=lambda item: item[1]["name"])

    for site_key, site_config in sorted_sites:
        base_url = site_config.get("base_search_url")
        if not base_url:
            continue
        site_config_dynamic = site_config.copy()
        site_config_dynamic["category_url"] = base_url.replace("{query}", encoded_query)

        await scrape_site(
            site_key,
            site_config_dynamic,
            engine,
            healing,
            validator,
            db,
            alerts,
            all_scraped_data,
            search_date,
            search_time,
            search_term,
            qwen=qwen,
        )

    # Save CSV
    if all_scraped_data:
        all_scraped_data.sort(key=lambda x: x["website"])
        safe_term = (
            "".join([c for c in search_term if c.isalnum() or c == " "])
            .rstrip()
            .replace(" ", "_")[:30]
        )
        csv_path = (
            DATA_DIR
            / f"price_comparison_{safe_term}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )

        fieldnames = [
            "Source",
            "Website Name",
            "Product Name",
            "Price (INR)",
            "Relevance Score",
            "Specifications",
            "Product Image URL",
            "Product Link",
            "Date",
            "Time",
        ]

        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in all_scraped_data:
                writer.writerow(
                    {
                        "Source": row.get("source", ""),
                        "Website Name": row.get("website", ""),
                        "Product Name": row.get("name", ""),
                        "Price (INR)": row.get("price_inr", ""),
                        "Relevance Score": row.get("_relevance_score", "N/A"),
                        "Specifications": row.get("specs", ""),
                        "Product Image URL": row.get("image_url", "") or "",
                        "Product Link": row.get("link", ""),
                        "Date": row.get("date", ""),
                        "Time": row.get("time", ""),
                    }
                )

        print(f"\n{CYAN}{'=' * 65}{RESET}")
        print(
            f"{GREEN}{BOLD}🎉 SUCCESS! Saved {len(all_scraped_data)} items total.{RESET}"
        )
        print(f"{GREEN}📁 CSV saved at: {csv_path}{RESET}")
        print(f"{CYAN}{'=' * 65}{RESET}")

        # Open Menu
        handle_results_menu(all_scraped_data, csv_path, search_term)
    else:
        print(f"\n{RED}✗ NO DATA COLLECTED. Sites likely blocked the scraper.{RESET}")

    db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Self-Healing E-Commerce Price Comparator"
    )
    args = parser.parse_args()

    setup_logging()
    try:
        asyncio.run(run_interactive_search())
    except KeyboardInterrupt:
        print(f"\n{RED}Scraping cancelled by user.{RESET}")

    import time

    time.sleep(1)


if __name__ == "__main__":
    main()
