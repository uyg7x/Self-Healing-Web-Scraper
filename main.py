"""
MAIN RUNNER (Interactive Price Comparator with Links, Specs & INR)
"""

import sys
import logging
import csv
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from config import SITES_CONFIG, LOG_LEVEL, LOG_FILE, DATA_DIR, CURRENCY_TO_INR
from scraper_engine import ScraperEngine
from self_healing import SelfHealingSystem
from validators import DataValidator
from database import Database
from alerts import AlertSystem

def setup_logging():
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(str(LOG_FILE)),
            logging.StreamHandler(sys.stdout),
        ]
    )
    return logging.getLogger(__name__)

def scrape_site(site_key, site_config, engine, healing, validator, db, alerts, results_collector, search_date, search_time):
    logger = logging.getLogger(__name__)
    site_name = site_config["name"]
    target_url = site_config["category_url"]
    
    print(f"🔎 Searching {site_name}...")
    
    selectors = healing.get_prioritized_selectors(site_key, site_config["selectors"])
    html = engine.fetch_page(target_url, js_required=site_config["js_required"])
    if not html:
        logger.error(f"Failed to fetch {site_name} (Blocked/CAPTCHA)")
        return
    
    # base_url = site root, used to build full product links
    products, scrape_info = engine.extract_data(html, site_config["url"], selectors, site_config["regex_fallback"])
    if not products:
        logger.warning(f"No products found on {site_name}")
        return
    
    valid_products = validator.filter_products(products)
    if not valid_products:
        logger.warning(f"All products failed validation on {site_name}")
        return
    
    # Convert price to Indian Rupees
    rate = CURRENCY_TO_INR.get(site_config.get("currency", "INR"), 1.0)
    
    for p in valid_products:
        p['website'] = site_name
        p['date'] = search_date
        p['time'] = search_time
        if p.get('price_float'):
            p['price_inr'] = f"₹{p['price_float'] * rate:,.0f}"
        else:
            p['price_inr'] = "N/A"
        
    results_collector.extend(valid_products)
    
    db.save_products(valid_products, site_key, scrape_info)
    healing.record_success(site_key, scrape_info.get("strategy_index", 0), scrape_info.get("method", "unknown"))
    print(f"   ✓ Found {len(valid_products)} products on {site_name}")

def run_interactive_search():
    print("\n" + "="*65)
    print("🤖  SELF-HEALING E-COMMERCE PRICE COMPARATOR (v3)")
    print("="*65)
    print("⚠️  REALITY CHECK: Amazon, Flipkart, Ajio, Meesho, ShopClues,")
    print("GlowRoad & Goodreads have heavy anti-bot systems. If they fail,")
    print("that is NORMAL. Robu.in, Sapna Online & BooksToScrape usually work.")
    print("="*65 + "\n")
    
    search_term = input("🔍 Enter the product you want to search for: ").strip()
    if not search_term:
        print("❌ No product entered. Exiting.")
        return
        
    print(f"\n🚀 Searching '{search_term}' across {len(SITES_CONFIG)} platforms...\n")
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
        scrape_site(site_key, site_config_dynamic, engine, healing, validator, db, alerts, all_scraped_data, search_date, search_time)
        
    # --- EXPORT TO CSV ---
    if all_scraped_data:
        all_scraped_data.sort(key=lambda x: x['website'])
        
        safe_term = "".join([c for c in search_term if c.isalpha() or c.isdigit() or c==' ']).rstrip().replace(" ", "_")[:30]
        csv_path = DATA_DIR / f"price_comparison_{safe_term}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
            fieldnames = ['Website Name', 'Product Name', 'Price (INR)', 'Specifications', 'Product Link', 'Date', 'Time']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in all_scraped_data:
                writer.writerow({
                    'Website Name': row.get('website'),
                    'Product Name': row.get('name'),
                    'Price (INR)': row.get('price_inr'),
                    'Specifications': row.get('specs'),
                    'Product Link': row.get('link'),
                    'Date': row.get('date'),
                    'Time': row.get('time')
                })
        
        print("\n" + "="*65)
        print(f"🎉 SUCCESS! Saved {len(all_scraped_data)} items.")
        print(f"📁 CSV saved at: {csv_path}")
        print("="*65 + "\n")
    else:
        print("\n⚠️ NO DATA COLLECTED. Sites likely blocked the scraper. Check data/scraper.log")
            
    db.close()

def main():
    setup_logging()
    run_interactive_search()

if __name__ == "__main__":
    main()