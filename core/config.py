import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "scraper.db"
SELECTOR_HISTORY_PATH = DATA_DIR / "selector_history.json"

DATA_DIR.mkdir(exist_ok=True)

LOG_LEVEL = "INFO"
LOG_FILE = DATA_DIR / "scraper.log"

MAX_RETRIES = 2
REQUEST_TIMEOUT = 30

DELAY_CONFIG = {
    "page_turn": {
        "base": 1.8,
        "sigma": 0.65,
        "hard_min": 0.9,
        "hard_max": 22.0,
        "long_pause_chance": 0.12,
        "long_pause_range": (3.0, 9.0),
    },
    "between_sites": {
        "base": 4.0,
        "sigma": 0.5,
        "hard_min": 2.0,
        "hard_max": 15.0,
    },
    "after_block_min": 20.0,
    "after_block_max": 55.0,
}

MAX_PAGES_PER_SITE = 30
EARLY_STOP_AFTER_EMPTY_PAGES = 2

PROXY_LIST = []

PROXY_CONFIG = {
    "enabled": len(PROXY_LIST) > 0,
    "proxies": PROXY_LIST,
    "rotation_strategy": "random",
    "health_check": True,
    "health_check_timeout": 10,
    "max_failures": 3,
}

EMAIL_CONFIG = {
    "enabled": False,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "email": "",
    "password": "",
    "recipient": "",
}
SCHEDULE_TIME = "09:00"

CURRENCY_TO_INR = {"INR": 1.0, "USD": 88.0, "GBP": 112.0}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

SITES_CONFIG = {
    "robu": {
        "name": "Robu.in",
        "url": "https://robu.in",
        "base_search_url": "https://robu.in/?s={query}",
        "js_required": True,
        "currency": "INR",
        "crawl_mode": "browser",
        "next_selector": "a.next.page-numbers",
        "pagination": {"type": "next_button", "max_pages": MAX_PAGES_PER_SITE},
        "selectors": [
            {
                "product_name": ".woocommerce-loop-product__title, h2.product-title",
                "price": ".price .amount, span.amount",
            },
        ],
        "regex_fallback": {
            "product_name": r'class="woocommerce-loop-product__title"[^>]*>([^<]{5,})<',
            "price": r'₹([\d,]+)',
        },
    },

    "amazon": {
        "name": "Amazon India",
        "url": "https://www.amazon.in",
        "base_search_url": "https://www.amazon.in/s?k={query}",
        "js_required": True,
        "currency": "INR",
        "crawl_mode": "browser",
        "next_selector": "a.s-pagination-next:not(.s-pagination-disabled)",
        "pagination": {"type": "next_button", "max_pages": MAX_PAGES_PER_SITE},
        "selectors": [
            {
                "product_name": "div[data-component-type='s-search-result'] h2 a span, h2 a span, h2 span",
                "price": "span.a-price span.a-offscreen",
                "specs": "div.a-row.a-size-base.a-color-secondary",
            },
        ],
        "regex_fallback": {
            "product_name": r'<span[^>]*class="[^"]*a-text-normal[^"]*"[^>]*>([^<]{10,})</span>',
            "price": r'₹([\d,]+)',
        },
    },

    "flipkart": {
        "name": "Flipkart",
        "url": "https://www.flipkart.com",
        "base_search_url": "https://www.flipkart.com/search?q={query}",
        "js_required": True,
        "currency": "INR",
        "crawl_mode": "browser",
        "next_selector": "a[class*='_9QVEpD'], a:has-text('Next')",
        "pagination": {"type": "next_button", "max_pages": MAX_PAGES_PER_SITE},
        "selectors": [
            {
                "product_name": "div.KzDlHZ, div._4rR01T, a.s1Q9wV",
                "price": "div.Nx9bqj, div._30jeq3",
                "specs": "ul._1xgFaf li",
            },
        ],
        "regex_fallback": {
            "product_name": r'title="([^"]{10,})"',
            "price": r'₹([\d,]+)',
        },
    },

    "alibaba": {
        "name": "Alibaba",
        "url": "https://www.alibaba.com",
        "base_search_url": "https://www.alibaba.com/trade/search?SearchText={query}",
        "js_required": True,
        "currency": "USD",
        "crawl_mode": "browser",
        "extractor": "alibaba",
        "next_selector": (
            "a[href*='page=']:not([href*='page=1']), "
            "button.fy26-pagination-arrow-next, "
            "a.fy26-pagination-arrow-next, "
            "li.fy26-pagination-item:last-child a"
        ),
        "pagination": {
            "type": "next_button",
            "url_template": "https://www.alibaba.com/trade/search?SearchText={query}&page={page}",
            "max_pages": MAX_PAGES_PER_SITE,
        },

        "selectors": [
            {
                "product_name": (
                    "div[data-spm='normal_offer'] h2, "
                    "div[data-spm='normal_offer'] .search-card-e-title, "
                    ".search-card-item h2, "
                    ".search-card-item .search-card-e-title, "
                    "div.fy23-search-card h2, "
                    "div.fy23-search-card .search-card-e-title, "
                    "h2.search-card-e-title"
                ),
                "price": (
                    "div[data-spm='normal_offer'] .search-card-e-price-main, "
                    ".search-card-item .search-card-e-price-main, "
                    "div.fy23-search-card .search-card-e-price-main, "
                    ".search-card-e-price-main"
                ),
                "specs": (
                    "div[data-spm='normal_offer'] .search-card-m-sale-features__item, "
                    ".search-card-item .search-card-m-sale-features__item, "
                    ".search-card-e-company"
                ),
            },
        ],
        "regex_fallback": {
            "product_name": r'"subject"\s*:\s*"([^"]{10,})"',
            "price": r'"price"\s*:\s*"?([\d.]+)"?',
        },
    },

    "ebay": {
        "name": "eBay",
        "url": "https://www.ebay.com",
        "base_search_url": "https://www.ebay.com/sch/i.html?_nkw={query}",
        "js_required": True,
        "currency": "USD",
        "crawl_mode": "browser",
        "extractor": "ebay",
        "next_selector": "a.pagination__next, a[aria-label='Next']",
        "pagination": {
            "type": "next_button",
            "url_template": "https://www.ebay.com/sch/i.html?_nkw={query}&_pgn={page}",
            "max_pages": MAX_PAGES_PER_SITE,
        },
        "selectors": [
            {
                "product_name": "li.s-card .s-card__title, li.s-item .s-item__title",
                "price": ".s-card__price, .s-item__price",
            },
        ],
        "regex_fallback": {
            "product_name": r'title="([^"]{10,})"',
            "price": r'\$([\d,.]+)',
        },
    },

    "newegg": {
        "name": "Newegg",
        "url": "https://www.newegg.com",
        "base_search_url": "https://www.newegg.com/p/pl?d={query}",
        "js_required": True,
        "currency": "USD",
        "crawl_mode": "browser",
        "extractor": "newegg",
        "next_selector": "button[class*='next'], a[class*='next'], a[title='Next']",
        "pagination": {
            "type": "next_button",
            "url_template": "https://www.newegg.com/p/pl?d={query}&page={page}",
            "max_pages": MAX_PAGES_PER_SITE,
        },
        "selectors": [
            {
                "product_name": ".item-cell .item-title",
                "price": ".item-cell .price-current",
                "specs": ".item-cell .item-features li",
            },
        ],
        "regex_fallback": {
            "product_name": r'title="([^"]{10,})"',
            "price": r'\$([\d,]+)',
        },
    },

    "temu": {
        "name": "Temu",
        "url": "https://www.temu.com",
        "base_search_url": "https://www.temu.com/search_result.html?search_key={query}",
        "js_required": True,
        "currency": "USD",
        "crawl_mode": "browser",
        "extractor": "temu",
        "next_selector": "a[aria-label='Next'], span:has-text('Next')",
        "pagination": {
            "type": "next_button",
            "max_pages": MAX_PAGES_PER_SITE,
        },
        "selectors": [
            {
                "product_name": "div[class*='product-card'] a[class*='title'], div[data-uniqid] a[class*='title']",
                "price": "div[class*='product-card'] span[class*='price'], div[data-uniqid] span[class*='price']",
            },
        ],
        "regex_fallback": {
            "product_name": r'"title"\s*:\s*"([^"]{10,})"',
            "price": r'"price"\s*:\s*"?([\d.]+)"?',
        },
    },
}

VALIDATION_RULES = {
    "product_name": {
        "min_length": 5,
        "max_length": 200,
        "forbidden_patterns": [r"^(click|subscribe|login)", r"^https?://"],
    },
    "price": {
        "min_length": 1,
        "max_length": 20,
        "forbidden_patterns": [r"^[^0-9]*$"],
    },
}

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-1.5-flash-latest"
LLM_HTML_MAX_CHARS = 20000

COE_AI_CONFIG = {
    "enabled": True,
    "base_url": "",
    "api_key": os.getenv("COE_AI_KEY", ""),
    "model": "qwen3.6",
    "max_tokens": 2048,
    "html_max_chars": 30000,
}

AI_BACKENDS_AVAILABLE = {
    "gemini": True,
    "qwen": True,
}
