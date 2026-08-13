"""
CONFIGURATION FILE
Self-Healing Price Comparison - Demo Version
Sites ordered: Safe demos first, hard sites last
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "scraper.db"
SELECTOR_HISTORY_PATH = DATA_DIR / "selector_history.json"

DATA_DIR.mkdir(exist_ok=True)

LOG_LEVEL = "INFO"
LOG_FILE = DATA_DIR / "scraper.log"

MAX_RETRIES = 2
RETRY_DELAY = 3
REQUEST_TIMEOUT = 30
DELAY_BETWEEN_REQUESTS = (3, 6)

PROXY_CONFIG = {"enabled": False, "proxies": []}
EMAIL_CONFIG = {"enabled": False, "smtp_server": "smtp.gmail.com", "smtp_port": 587, "email": "", "password": "", "recipient": ""}
SCHEDULE_TIME = "09:00"

CURRENCY_TO_INR = {
    "INR": 1.0,
    "USD": 88.0,
    "GBP": 112.0,
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# Only 4 sites - ordered for demo strategy
SITES_CONFIG = {
    "robu": {
        "name": "Robu.in",
        "url": "https://robu.in",
        "base_search_url": "https://robu.in/?s={query}",
        "js_required": False,
        "currency": "INR",
        "selectors": [
            {"product_name": ".woocommerce-loop-product__title, h2.product-title",
             "price": ".price .amount, span.amount"},
        ],
        "regex_fallback": {"product_name": r'class="woocommerce-loop-product__title"[^>]*>([^<]{5,})<', "price": r'₹([\d,]+)'},
    },
    "books_toscrape": {
        "name": "Books to Scrape (Practice)",
        "url": "http://books.toscrape.com",
        "base_search_url": "http://books.toscrape.com/catalogue/page-1.html",
        "js_required": False,
        "currency": "GBP",
        "selectors": [
            {"product_name": "article.product_pod h3 a", "price": "p.price_color", "specs": "p.instock.availability"},
        ],
        "regex_fallback": {"product_name": r'<h3><a[^>]*title="([^"]+)"', "price": r'£([\d.]+)'},
    },
    "amazon": {
        "name": "Amazon India",
        "url": "https://www.amazon.in",
        "base_search_url": "https://www.amazon.in/s?k={query}",
        "js_required": True,
        "currency": "INR",
        "selectors": [
            {"product_name": "h2 a span.a-text-normal, span.a-size-medium",
             "price": "span.a-price .a-offscreen"},
        ],
        "regex_fallback": {"product_name": r'<span[^>]*class="[^"]*a-text-normal[^"]*"[^>]*>([^<]{10,})</span>', "price": r'₹([\d,]+)'},
    },
    "flipkart": {
        "name": "Flipkart",
        "url": "https://www.flipkart.com",
        "base_search_url": "https://www.flipkart.com/search?q={query}",
        "js_required": True,
        "currency": "INR",
        "selectors": [
            {"product_name": "div.KzDlHZ, div._4rR01T, a.s1Q9wV",
             "price": "div.Nx9bqj, div._30jeq3",
             "specs": "ul._1xgFaf li"},
        ],
        "regex_fallback": {"product_name": r'title="([^"]{10,})"', "price": r'₹([\d,]+)'},
    },
}

VALIDATION_RULES = {
    "product_name": {"min_length": 5, "max_length": 200, "forbidden_patterns": [r"^(click|subscribe|login)", r"^https?://"]},
    "price": {"min_length": 1, "max_length": 20, "forbidden_patterns": [r"^[^0-9]*$"]},
}

# ----------------------------------------------------------------------
# LLM HEALER (Gemini) SETTINGS
# ----------------------------------------------------------------------
# Used by llm_healer.py as the 5th and final fallback strategy.
#
# We read the API key ONLY from the environment variable GEMINI_API_KEY.
# NEVER hardcode your key here -- it will be pushed to GitHub and can
# be stolen. Instead, do ONE of the following on your local machine:
#
#   1. Set it in your shell before running:
#        Windows PowerShell:
#          $env:GEMINI_API_KEY = "AIzaSy...your_key_here"
#        macOS / Linux:
#          export GEMINI_API_KEY="AIzaSy...your_key_here"
#
#   2. Put it in a .env file at the project root (already in .gitignore):
#          GEMINI_API_KEY=AIzaSy...your_key_here
#
# Get a free key in ~30 seconds at:
#   https://aistudio.google.com/apikey
# ----------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Free-tier model. gemini-2.0-flash is fast, cheap, and great for this.
GEMINI_MODEL = "gemini-2.0-flash"

# How many characters of cleaned HTML to send to Gemini.
# 20,000 is a safe balance between "enough context" and "stays under
# free-tier token limits". Bump this up if you have a paid plan.
LLM_HTML_MAX_CHARS = 20000