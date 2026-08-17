"""
MAIN RUNNER (Interactive Price Comparator with Links, Specs & INR)

Features:
- Shows which platform (Amazon, Flipkart, Robu, ...) AND which strategy
  (JSON-LD, CSS, regex, self-heal, LLM/Gemini) every product came from.
- Interactive AI mode: when a site's 4 traditional strategies all fail,
  the user is asked "Use AI (Gemini) for this site? [y/N]". Only if they
  answer 'y' do we call Gemini and stamp those products as
  "Gemini AI • llm".
"""

import sys
import io
import logging
import csv
import argparse
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

# CRITICAL: Fix Windows Unicode crashes (cp1252 error) for emojis and ₹ symbols
if sys.platform.startswith("win"):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    except (ValueError, AttributeError):
        pass
    try:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except (ValueError, AttributeError):
        pass

from config import SITES_CONFIG, LOG_LEVEL, LOG_FILE, DATA_DIR, CURRENCY_TO_INR
from scraper_engine import ScraperEngine
from self_healing import SelfHealingSystem
from validators import DataValidator
from database import Database
from alerts import AlertSystem

# ----------------------------------------------------------------------
# Display helpers — turn a strategy index/method into a friendly label
# ----------------------------------------------------------------------
STRATEGY_LABELS = {
    "json_ld":       "JSON-LD (structured data)",
    "css_selector":  "CSS selector",
    "regex":         "Regex fallback",
    "self_healing":  "Self-healing (fuzzy match)",
    "llm":           "Gemini AI (LLM)",
}

def format_source(website: str, method: str) -> str:
    """
    Build the "designation" string used in logs, terminal output and CSV.
    Example outputs:
        "Amazon India • CSS selector"
        "Robu.in • Gemini AI (LLM)"
    """
    label = STRATEGY_LABELS.get(method, method or "unknown")
    return f"{website} • {label}"


def setup_logging():
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
            logging.StreamHandler(sys.stderr),
        ]
    )
    return logging.getLogger(__name__)


def ask_user_yes_no(prompt: str, default: str = "n") -> bool:
    """
    Tiny helper: print a prompt, read y/n, return True/False.
    Empty Enter -> use the default ("n" by default).
    Accepts y/yes/n/no (case-insensitive).
    """
    suffix = "[y/N]" if default.lower() == "n" else "[Y/n]"
    try:
        ans = input(f"{prompt} {suffix}: ").strip().lower()
    except EOFError:
        return default == "y"
    if not ans:
        return default == "y"
    return ans in ("y", "yes")


def scrape_site(site_key, site_config, engine, healing, validator, db, alerts,
                results_collector, search_date, search_time, search_term,
                demo_mode=False):
    logger = logging.getLogger(__name__)
    site_name = site_config["name"]
    target_url = site_config["category_url"]

    print(f"\n  Searching {site_name}...")
    print(f"     URL: {target_url}")

    selectors = healing.get_prioritized_selectors(site_key, site_config["selectors"])

    # --- DEMO MODE: scramble CSS selectors to force the fallback cascade ---
    if demo_mode and site_config.get("selectors"):
        print(f"     [DEMO] Scrambling CSS selectors to simulate a site redesign...")
        original_selectors = selectors
        scrambled = []
        for sel in site_config["selectors"]:
            scrambled.append({k: v + "___BROKEN___" for k, v in sel.items()})
        selectors = scrambled
        logger.info(f"DEMO MODE: selectors scrambled for {site_name}")
    html = engine.fetch_page(target_url, js_required=site_config["js_required"])
    if not html:
        logger.error(f"Failed to fetch {site_name} (Blocked/CAPTCHA)")
        return

    # Try the 4 traditional strategies first (JSON-LD, CSS, regex, fuzzy).
    products, scrape_info = engine.extract_data(
        html, site_config["url"], selectors, site_config["regex_fallback"]
    )

    used_method = scrape_info.get("method", "")

    # If everything failed, optionally ask the user if they want AI mode.
    if not products:
        logger.warning(f"No products found on {site_name} using traditional methods.")
        print(f"     [WARN] No output found on {site_name} after 4 strategies.")

        if ask_user_yes_no(
            f"     No output found. Use LLM (Google Gemini) mode for {site_name}?",
            default="n",
        ):
            print(f"     Asking Gemini LLM to read {site_name}... (may take a few seconds)")
            products = engine.extract_with_llm(
                html, site_config["url"], search_hint=search_term
            )
            if products:
                used_method = "llm"
                scrape_info = {"strategy_index": -4, "method": "llm"}
                logger.info(
                    f"LLM HEALER SUCCEEDED on {site_name}! "
                    f"Found {len(products)} product(s) via Gemini."
                )
                print(f"     [OK] Gemini LLM returned {len(products)} product(s).")
            else:
                logger.warning(f"Gemini also returned nothing for {site_name}.")
                print(f"     [INFO] Gemini LLM also returned nothing for {site_name}.")
        else:
            print(f"     Skipping LLM mode for {site_name}.")
            return

    valid_products = validator.filter_products(products, search_term)
    if not valid_products:
        logger.warning(f"All products failed validation on {site_name}")
        return

    # Convert price to Indian Rupees + attach metadata
    rate = CURRENCY_TO_INR.get(site_config.get("currency", "INR"), 1.0)

    source_label = format_source(site_name, used_method)
    print(f"     [OK] {len(valid_products)} product(s) from: {source_label}")

    for p in valid_products:
        p['website'] = site_name
        # The "designation" string shown in terminal and CSV
        p['source'] = source_label
        # Raw pieces in case downstream code wants them separately
        p['extraction_method'] = used_method
        p['date'] = search_date
        p['time'] = search_time
        if p.get('price_float'):
            p['price_inr'] = f"₹{p['price_float'] * rate:,.0f}"
        else:
            p['price_inr'] = "N/A"

    results_collector.extend(valid_products)

    db.save_products(valid_products, site_key, scrape_info)
    healing.record_success(
        site_key,
        scrape_info.get("strategy_index", 0),
        scrape_info.get("method", "unknown"),
    )


def run_interactive_search(demo_mode=False):
    print("\n" + "=" * 65)
    print("  SELF-HEALING E-COMMERCE PRICE COMPARATOR")
    if demo_mode:
        print("  [DEMO MODE] CSS selectors will be scrambled to showcase")
        print("  the self-healing cascade (CSS -> Regex -> Fuzzy -> LLM).")
    print("=" * 65)
    print("  REALITY CHECK: Amazon, Flipkart, Ajio, Meesho, ShopClues,")
    print("  GlowRoad & Goodreads have heavy anti-bot systems. If they fail,")
    print("  that is NORMAL. Robu.in, Sapna Online & BooksToScrape usually work.")
    print("=" * 65)
    print("  When no products are found on a site, the scraper will")
    print("  automatically ask if you want to use LLM (Google Gemini) mode.")
    print("=" * 65 + "\n")

    search_term = input("  Enter the product you want to search for: ").strip()
    if not search_term:
        print("  No product entered. Exiting.")
        return

    print(f"\n  Searching '{search_term}' across {len(SITES_CONFIG)} platforms...\n")
    encoded_query = quote_plus(search_term)

    all_scraped_data = []
    engine = ScraperEngine()
    healing = SelfHealingSystem()
    validator = DataValidator()
    db = Database()
    alerts = AlertSystem()

    now = datetime.now()
    search_date = now.strftime("%Y-%m-%d")
    search_time = now.strftime("%H:%M:%S")

    sorted_sites = sorted(SITES_CONFIG.items(), key=lambda item: item[1]['name'])

    for site_key, site_config in sorted_sites:
        base_url = site_config.get("base_search_url")
        if not base_url:
            continue
        site_config_dynamic = site_config.copy()
        site_config_dynamic["category_url"] = base_url.replace("{query}", encoded_query)
        scrape_site(
            site_key, site_config_dynamic, engine, healing, validator, db, alerts,
            all_scraped_data, search_date, search_time, search_term,
            demo_mode=demo_mode,
        )

    # --- EXPORT TO CSV ---
    if all_scraped_data:
        all_scraped_data.sort(key=lambda x: x['website'])

        safe_term = "".join(
            [c for c in search_term if c.isalpha() or c.isdigit() or c == ' ']
        ).rstrip().replace(" ", "_")[:30]
        csv_path = DATA_DIR / f"price_comparison_{safe_term}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        # 'Source' is the new designation column (e.g. "Amazon India • CSS selector")
        fieldnames = [
            'Source',
            'Website Name',
            'Product Name',
            'Price (INR)',
            'Relevance Score',  # NEW: 0-100 score from the RelevanceScorer
            'Specifications',
            'Product Link',
            'Date',
            'Time',
        ]
        with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in all_scraped_data:
                writer.writerow({
                    'Source':           row.get('source', row.get('website', '')),
                    'Website Name':     row.get('website'),
                    'Product Name':     row.get('name'),
                    'Price (INR)':      row.get('price_inr'),
                    'Relevance Score':  row.get('_relevance_score', 'N/A'),
                    'Specifications':   row.get('specs'),
                    'Product Link':     row.get('link'),
                    'Date':             row.get('date'),
                    'Time':             row.get('time'),
                })

        # Pretty summary by source so the user can see designation at a glance
        print("\n" + "=" * 65)
        print("  RESULTS BY SOURCE (designation):")
        print("=" * 65)
        by_source = {}
        for row in all_scraped_data:
            src = row.get('source', row.get('website', 'Unknown'))
            by_source[src] = by_source.get(src, 0) + 1
        for src, count in sorted(by_source.items()):
            print(f"     {count:>3}  -  {src}")
        print("=" * 65)
        print(f"  SUCCESS! Saved {len(all_scraped_data)} items total.")
        print(f"  CSV saved at: {csv_path}")
        print("=" * 65 + "\n")
    else:
        print("\n  NO DATA COLLECTED. Sites likely blocked the scraper. Check data/scraper.log")

    db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Self-Healing E-Commerce Price Comparator",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Breakage simulator: scramble CSS selectors to demonstrate "
             "the self-healing fallback cascade (CSS -> Regex -> Fuzzy -> LLM).",
    )
    args = parser.parse_args()

    setup_logging()
    run_interactive_search(demo_mode=args.demo)


if __name__ == "__main__":
    main()
