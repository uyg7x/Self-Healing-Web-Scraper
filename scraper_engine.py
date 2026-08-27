"""
SCRAPER ENGINE
With TRUE Self-Healing: Fuzzy matching when all selectors fail
"""

import random
import time
import re
import json
import logging
from typing import Optional, Dict, List, Tuple
from urllib.parse import urljoin
from difflib import SequenceMatcher

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from config import (
    USER_AGENTS, MAX_RETRIES, RETRY_DELAY, REQUEST_TIMEOUT,
    DELAY_BETWEEN_REQUESTS, PROXY_CONFIG
)
# 5th and final fallback: ask Google Gemini to "read" the page for us.
# We only import it here (not in config) so the rest of the engine stays
# importable even if the user hasn't installed google-generativeai yet.
from llm_healer import LLMHealer

logger = logging.getLogger(__name__)

class ScraperEngine:
    def __init__(self):
        # Use a modern, real browser User-Agent (Chrome 120 for Robu.in compatibility)
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.session = requests.Session()
        # Inject stealth headers immediately
        self.session.headers.update(self._get_stealth_headers())

        self.proxy = None
        if PROXY_CONFIG.get("enabled") and PROXY_CONFIG.get("proxies"):
            self.proxy = random.choice(PROXY_CONFIG["proxies"])
            self.session.proxies = {"http": self.proxy, "https": self.proxy}

        # Lazily build the LLM healer. It is only USED if every other
        # strategy fails, so it doesn't slow down the happy path.
        self.llm_healer = LLMHealer()

    def _get_stealth_headers(self):
        """Returns headers that mimic a real human browser to bypass 403 blocks."""
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }

    @staticmethod
    def _looks_binary(html: str) -> bool:
        """
        True if the page is mostly non-printable bytes (bad decode).
        Relaxed threshold so real pages like BooksToScrape aren't rejected.
        """
        if not html or len(html) < 100:
            return True
        
        # Sample the first 5000 chars
        sample = html[:5000]
        printable = sum(1 for c in sample if c.isprintable() or c in "\n\r\t ")
        ratio = printable / len(sample)
        
        # Only reject if LESS than 60% printable (was too strict before)
        return ratio < 0.6

    def fetch_page(self, url: str, js_required: bool = False) -> Optional[str]:
        delay = random.uniform(*DELAY_BETWEEN_REQUESTS)
        time.sleep(delay)

        if js_required:
            return self._fetch_with_playwright(url)
        else:
            return self._fetch_with_requests(url)

    def _fetch_with_requests(self, url: str) -> Optional[str]:
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Fetching {url} (attempt {attempt + 1})")
                # Pass headers explicitly to ensure they're sent with each request
                response = self.session.get(url, headers=self._get_stealth_headers(), timeout=REQUEST_TIMEOUT)
                response.raise_for_status()

                # CRITICAL FIX: requests defaults to ISO-8859-1 which breaks UTF-8 sites like BooksToScrape
                if not response.encoding or response.encoding.lower() == "iso-8859-1":
                    response.encoding = response.apparent_encoding

                html_text = response.text
                
                # Check if response looks like binary garbage (bad decode)
                if self._looks_binary(html_text):
                    logger.warning(f"Response looks like binary data, retrying {url}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY * (attempt + 1))
                        continue
                    return None

                content = html_text.lower()
                if any(block in content for block in ["captcha", "robot check", "403 forbidden", "access denied"]):
                    logger.warning(f"Possible bot detection at {url}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY * (attempt + 1))
                        continue
                return html_text
            except requests.RequestException as e:
                logger.error(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
        return None
    
    def _fetch_with_playwright(self, url: str) -> Optional[str]:
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Fetching {url} with Playwright (attempt {attempt + 1})")
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
                    context = browser.new_context(user_agent=self.user_agent)
                    context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
                    page = context.new_page()
                    page.goto(url, timeout=REQUEST_TIMEOUT * 1000, wait_until="networkidle")
                    page.wait_for_timeout(3000)
                    html = page.content()
                    browser.close()
                    
                    # Check if response looks like binary garbage
                    if self._looks_binary(html):
                        logger.warning(f"Playwright response looks like binary data, retrying {url}")
                        if attempt < MAX_RETRIES - 1:
                            time.sleep(RETRY_DELAY * (attempt + 1))
                            continue
                        return None
                    
                    return html
            except Exception as e:
                logger.error(f"Playwright error: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (attempt + 1))
        return None
    
    def extract_data(self, html: str, base_url: str, selectors: List[Dict], regex_fallback: Dict) -> Tuple[List[Dict], Dict]:
        soup = BeautifulSoup(html, "html.parser")

        # 🔥 NEW STRATEGY 0: JSON-LD structured data (survives 90% of redesigns)
        logger.info("Trying JSON-LD structured data extraction...")
        products = self._extract_from_jsonld(soup, base_url)
        if products:
            logger.info(f"✓ JSON-LD succeeded! Found {len(products)} products")
            # JSON-LD often has MRP - validate and fix to get selling price
            products = [self._validate_selling_price(p, html) for p in products]
            products = self._recover_prices_from_html(products, html)
            return products, {"strategy_index": -3, "method": "json_ld"}

        # Try CSS selectors
        for i, selector_set in enumerate(selectors):
            logger.info(f"Trying selector strategy {i + 1}/{len(selectors)}")
            products = self._extract_with_selectors(soup, base_url, selector_set)
            if products:
                logger.info(f"✓ Strategy {i + 1} succeeded! Found {len(products)} products")
                products = [self._validate_selling_price(p, html) for p in products]
                products = self._recover_prices_from_html(products, html)
                return products, {"strategy_index": i, "method": "css_selector"}
            logger.info(f"✗ Strategy {i + 1} found no products...")

        # Try regex
        logger.warning("CSS failed. Trying regex fallback...")
        products = self._extract_with_regex(html, base_url, regex_fallback)
        if products:
            logger.info(f"✓ Regex succeeded! Found {len(products)} products")
            products = [self._validate_selling_price(p, html) for p in products]
            products = self._recover_prices_from_html(products, html)
            return products, {"strategy_index": -1, "method": "regex"}

        # 🔥 TRUE SELF-HEALING: Fuzzy matching when EVERYTHING fails
        logger.warning("All traditional methods failed. Activating SELF-HEALING mode...")
        products = self._self_heal_fuzzy_match(html, base_url)
        if products:
            logger.info(f"🧠 SELF-HEALING SUCCEEDED! Found {len(products)} products using intelligent matching")
            products = [self._validate_selling_price(p, html) for p in products]
            products = self._recover_prices_from_html(products, html)
            return products, {"strategy_index": -2, "method": "self_healing"}

        # 🤖 5th STRATEGY: Ask Google Gemini to read the page.
        # Only reached if JSON-LD, CSS, regex, and fuzzy self-healing ALL
        # returned nothing. We pass a search term hint (the last word(s)
        # from the URL, e.g. "harry-potter-books") to help Gemini focus.
        logger.warning(
            "All 4 strategies failed. Activating LLM HEALER (Gemini) as last resort..."
        )
        search_hint = self._guess_search_term(base_url)
        products = self.llm_healer.heal(html, search_hint)
        if products:
            logger.info(
                f"🤖 LLM HEALER SUCCEEDED! Found {len(products)} product(s) via Gemini."
            )
            # Best-effort price cleanup, same as the other strategies.
            try:
                products = [self._validate_selling_price(p, html) for p in products]
                products = self._recover_prices_from_html(products, html)
            except Exception as e:
                logger.debug(f"LLMHealer: post-processing skipped due to: {e}")
            return products, {"strategy_index": -4, "method": "llm"}

        return [], {}

    def _recover_prices_from_html(self, products: List[Dict], html: str) -> List[Dict]:
        """
        🔥 PRICE RECOVERY: When products were found but prices are N/A,
        scan the raw HTML for price symbols near each product link.
        This catches prices that are loaded dynamically but appear in HTML.

        SMART PRICE LOGIC:
        - Prefer "selling price" (current price) over MRP/original price
        - Look for price patterns with strikethrough/old-price indicators
        - If multiple prices found, pick the LOWER one (usually the deal)
        """
        if not products or not html:
            return products

        # Find all price occurrences with their positions AND context
        price_patterns = [
            (r'₹\s*([\d,]+(?:\.\d{2})?)', '₹'),
            (r'Rs\.?\s*([\d,]+(?:\.\d{2})?)', 'Rs'),
            (r'INR\s*([\d,]+(?:\.\d{2})?)', 'INR'),
            (r'\$\s*([\d,]+(?:\.\d{2})?)', '$'),
        ]

        # First pass: collect all prices with HTML context
        all_prices = []
        for pattern, symbol in price_patterns:
            for match in re.finditer(pattern, html):
                price_str = match.group(1).replace(',', '')
                try:
                    price_val = float(price_str)
                except ValueError:
                    continue

                # Get surrounding HTML context (100 chars before/after)
                context_start = max(0, match.start() - 200)
                context_end = min(len(html), match.end() + 50)
                context = html[context_start:context_end].lower()

                # Detect if this is an MRP/original price (not selling price)
                is_mrp = any(marker in context for marker in [
                    'strike', 'line-through', 'original', 'mrp', 'was',
                    'crossed', 'old-price', 'compare-at', 'list-price',
                    '_3auQ3N', '_2pXp4L'  # Flipkart's MRP CSS classes
                ])

                all_prices.append({
                    'position': match.start(),
                    'price': price_str,
                    'price_val': price_val,
                    'symbol': symbol,
                    'full': match.group(0),
                    'is_mrp': is_mrp
                })

        # Filter: prefer non-MRP prices, but keep all as fallback
        selling_prices = [p for p in all_prices if not p['is_mrp']]
        logger.info(
            f"Price recovery: {len(all_prices)} total, "
            f"{len(selling_prices)} are selling prices (not MRP)"
        )

        # For each product with N/A price, find the nearest SELLING price
        for product in products:
            if product.get('price') and product['price'] != 'N/A':
                # Even if JSON-LD gave a price, verify it's not MRP
                # If the existing price looks like MRP, try to find a better one
                continue  # For now, trust JSON-LD's price if it gave one

            # Find product link position in HTML
            link = product.get('link', '')
            product_pos = -1
            if link and link != 'N/A':
                link_slug = link.split('/')[-1].split('?')[0][:30] if link else ''
                if link_slug:
                    pos = html.find(link_slug)
                    if pos > 0:
                        product_pos = pos

            # If no link found, assign prices sequentially
            if product_pos < 0:
                try:
                    idx = products.index(product)
                    if idx < len(all_prices):
                        # Prefer selling prices over MRP
                        if idx < len(selling_prices):
                            loc = selling_prices[idx]
                        else:
                            loc = all_prices[idx]
                        product['price'] = f"{loc['symbol']}{loc['price']}"
                        try:
                            product['price_float'] = float(loc['price'])
                        except ValueError:
                            pass
                        continue
                except ValueError:
                    continue

            # Find the closest SELLING price to this product's position
            closest_price = None
            min_distance = float('inf')
            search_window = 2000

            # First try selling prices only
            for loc in selling_prices:
                distance = abs(loc['position'] - product_pos)
                if distance < min_distance and distance < search_window:
                    min_distance = distance
                    closest_price = loc

            # If no selling price found nearby, fall back to any price
            if not closest_price:
                for loc in all_prices:
                    distance = abs(loc['position'] - product_pos)
                    if distance < min_distance and distance < search_window:
                        min_distance = distance
                        closest_price = loc

            if closest_price:
                product['price'] = f"{closest_price['symbol']}{closest_price['price']}"
                try:
                    product['price_float'] = float(closest_price['price'])
                except ValueError:
                    pass
                mrp_note = " [was MRP]" if closest_price['is_mrp'] else ""
                logger.debug(
                    f"Recovered price {product['price']}{mrp_note} "
                    f"for {product.get('name', '')[:30]}"
                )

        return products

    def _validate_selling_price(self, product: Dict, html: str) -> Dict:
        """
        🔥 PRICE VALIDATION: For a product that has a price (from JSON-LD),
        verify it's the selling price, not MRP. If it looks like MRP,
        try to find a better (lower) price nearby in the HTML.
        """
        price_str = product.get('price', '')
        if price_str == 'N/A' or not price_str:
            return product

        price_float = product.get('price_float', 0)
        if not price_float or price_float < 100:
            return product  # Skip if no real price

        # Get product link slug
        link = product.get('link', '')
        if not link or link == 'N/A':
            return product

        link_slug = link.split('/')[-1].split('?')[0][:30]
        product_pos = html.find(link_slug)
        if product_pos < 0:
            return product

        # Look for prices AFTER this product's link (next product's prices are below)
        # and BEFORE the next product link
        window_end = min(len(html), product_pos + 1500)
        window_html = html[product_pos:window_end]

        # Find all ₹ prices in this window
        prices_in_window = []
        for match in re.finditer(r'₹\s*([\d,]+(?:\.\d{2})?)', window_html):
            price_val_str = match.group(1).replace(',', '')
            try:
                price_val = float(price_val_str)
                if price_val >= 100:  # Reasonable price
                    prices_in_window.append(price_val)
            except ValueError:
                continue

        if not prices_in_window:
            return product

        # If current price is higher than the LOWEST price in window,
        # the current price is likely MRP - replace with the lower one
        lowest = min(prices_in_window)
        if price_float > lowest * 1.05:  # 5% margin to allow tiny differences
            logger.debug(
                f"Price {price_float} looks like MRP, "
                f"using selling price {lowest} for {product.get('name', '')[:30]}"
            )
            product['price'] = f"₹{lowest:,.0f}"
            product['price_float'] = lowest

        return product

    def _extract_from_jsonld(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """
        🔥 JSON-LD / Schema.org structured data extractor.

        Modern e-commerce sites embed product data in:
        <script type="application/ld+json">{"@type":"Product","name":"...","offers":{"price":"..."}}</script>

        This survives CSS/HTML redesigns because it's machine-readable metadata.
        """
        products = []
        try:
            scripts = soup.find_all("script", type="application/ld+json")
            if not scripts:
                return []

            logger.info(f"Found {len(scripts)} JSON-LD script(s). Parsing...")

            for script in scripts:
                try:
                    data = json.loads(script.string or "{}")
                except (json.JSONDecodeError, TypeError):
                    continue

                # Handle both single objects and arrays (and @graph lists)
                items = []
                if isinstance(data, dict):
                    if "@graph" in data:
                        items = data["@graph"]
                    else:
                        items = [data]
                elif isinstance(data, list):
                    items = data

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    item_type = item.get("@type", "").lower()

                    # Unwrap ItemList -> listItem.listItem (nested Product)
                    if "itemlist" in item_type:
                        for list_item in item.get("itemListElement", []):
                            if isinstance(list_item, dict):
                                nested = list_item.get("listItem") or list_item.get("item") or list_item
                                if isinstance(nested, dict):
                                    p = self._parse_jsonld_product(nested, base_url)
                                    if p:
                                        products.append(p)
                        continue

                    # Accept Product, IndividualProduct, or nested in Offer
                    if "product" not in item_type and "offer" not in item_type:
                        continue

                    product = self._parse_jsonld_product(item, base_url)
                    if product:
                        products.append(product)

        except Exception as e:
            logger.error(f"JSON-LD parse error: {e}")

        return products

    def _parse_jsonld_product(self, item: Dict, base_url: str) -> Optional[Dict]:
        """Parse a single Product JSON-LD object into our product dict."""
        try:
            name = item.get("name", "").strip()
            if not name:
                return None

            # Price can be nested in "offers" (dict or list) or top-level
            price = None
            currency = None
            offers = item.get("offers")
            if isinstance(offers, dict):
                price = offers.get("price")
                currency = offers.get("priceCurrency")
            elif isinstance(offers, list) and offers:
                first = offers[0]
                if isinstance(first, dict):
                    price = first.get("price")
                    currency = first.get("priceCurrency")
            elif item.get("price"):
                price = item.get("price")
                currency = item.get("priceCurrency")

            # Fallback: try to parse from description if no structured price
            if price is None:
                desc = item.get("description", "")
                m = re.search(r"[\d,]+\.?\d*", desc.replace(",", ""))
                if m:
                    price = m.group()

            # Build display price string
            price_str = "N/A"
            if price is not None:
                symbols = {"INR": "₹", "USD": "$", "GBP": "£", "EUR": "€"}
                sym = symbols.get(currency, "")
                price_str = f"{sym}{price}" if sym else f"{currency} {price}"

            # Link
            link = item.get("url") or item.get("@id") or "N/A"
            if link != "N/A" and not link.startswith("http"):
                link = urljoin(base_url, link)

            # Specs from description or additionalProperty
            specs = "N/A"
            if item.get("description"):
                specs = item["description"][:200]
            elif item.get("sku"):
                specs = f"SKU: {item['sku']}"

            return {
                "name": name,
                "price": price_str,
                "price_float": self._safe_float(price),
                "link": link,
                "specs": specs,
                "method": "json_ld",
            }
        except Exception as e:
            logger.debug(f"JSON-LD product parse error: {e}")
            return None

    def _safe_float(self, val) -> Optional[float]:
        if val is None:
            return None
        try:
            return float(str(val).replace(",", ""))
        except (ValueError, TypeError):
            return None

    def _extract_with_selectors(self, soup: BeautifulSoup, base_url: str, selectors: Dict) -> List[Dict]:
        products = []
        try:
            name_elements = soup.select(selectors["product_name"])
            if not name_elements:
                return []
            
            for name_elem in name_elements[:20]: 
                product = {}
                name = name_elem.get_text(strip=True)
                
                a_tag = name_elem if name_elem.name == "a" else (name_elem.find_parent("a") or name_elem.find("a"))
                
                if a_tag and a_tag.get("title") and len(a_tag["title"]) > len(name):
                    name = a_tag["title"]
                
                if not name or len(name) < 5:
                    continue
                product["name"] = name
                
                if a_tag and a_tag.get("href"):
                    product["link"] = urljoin(base_url, a_tag["href"])
                else:
                    product["link"] = "N/A"
                
                price = self._find_nearby_price(name_elem, selectors.get("price"))
                product["price"] = price if price else "N/A"
                
                specs = self._find_nearby_specs(name_elem, selectors.get("specs"))
                product["specs"] = specs if specs else "N/A"
                
                # Extract product image
                image_url = self._extract_product_image(name_elem, base_url)
                product["image_url"] = image_url if image_url else "N/A"
                
                products.append(product)
                    
        except Exception as e:
            logger.error(f"Selector error: {e}")
        return products
    
    def _find_nearby_price(self, name_elem, price_selector: str) -> Optional[str]:
        if not price_selector:
            return None
        try:
            container = name_elem.find_parent(["div", "li", "article"])
            if container:
                price_elem = container.select_one(price_selector)
                if price_elem:
                    return price_elem.get_text(strip=True)
        except:
            pass
        return None
    
    def _find_nearby_specs(self, name_elem, specs_selector: str) -> Optional[str]:
        if not specs_selector:
            return None
        try:
            container = name_elem.find_parent(["div", "li", "article"])
            if container:
                spec_elems = container.select(specs_selector)
                if spec_elems:
                    return " | ".join(e.get_text(strip=True) for e in spec_elems[:4])
        except:
            pass
        return None
    
    def _extract_product_image(self, name_elem, base_url: str) -> Optional[str]:
        """Extract product image URL from element and its parents."""
        try:
            # Try data-src first (common lazy-load pattern)
            for img in name_elem.find_all("img", recursive=True):
                src = img.get("data-src") or img.get("src") or img.get("data-lazy") or img.get("data-original")
                if src and src.startswith("data:"):
                    continue  # Skip base64 inline images
                if src:
                    return urljoin(base_url, src)
            
            # Try parent container for product card images
            container = name_elem.find_parent(["div", "li", "article", "a"])
            if container:
                for img in container.find_all("img", recursive=True):
                    src = img.get("data-src") or img.get("src") or img.get("data-lazy") or img.get("data-original")
                    if src and src.startswith("data:"):
                        continue
                    if src:
                        return urljoin(base_url, src)
        except Exception as e:
            logger.debug(f"Image extraction error: {e}")
        return None
    
    def _extract_with_regex(self, html: str, base_url: str, patterns: Dict) -> List[Dict]:
        products = []
        try:
            names = re.findall(patterns["product_name"], html) if patterns.get("product_name") else []
            prices = re.findall(patterns["price"], html) if patterns.get("price") else []
            links = re.findall(patterns.get("link", r'href="([^"]+)"'), html) if patterns.get("link") else []
            
            for i in range(min(len(names), 20)):
                product = {
                    "name": names[i],
                    "price": prices[i] if i < len(prices) else "N/A",
                    "link": urljoin(base_url, links[i]) if i < len(links) else "N/A",
                    "image_url": "N/A",
                    "specs": "N/A",
                }
                if len(product["name"]) >= 5:
                    products.append(product)
        except Exception as e:
            logger.error(f"Regex error: {e}")
        return products
    
    # 🔥 THE KILLER FEATURE: True Self-Healing
    def _self_heal_fuzzy_match(self, html: str, base_url: str) -> List[Dict]:
        """
        When all selectors fail, intelligently find products by:
        1. Finding all price symbols (₹, $, £)
        2. Scanning nearby text for product names
        3. Scoring matches based on proximity and quality
        """
        soup = BeautifulSoup(html, "html.parser")
        products = []
        
        # Step 1: Find all price patterns (expanded to catch more redesigns)
        price_patterns = [
            r'₹\s*[\d,]+(?:\.\d{2})?',           # ₹1,299
            r'\$\s*[\d,]+(?:\.\d{2})?',           # $12.99
            r'£\s*[\d,]+(?:\.\d{2})?',            # £9.99
            r'Rs\.?\s*[\d,]+(?:\.\d{2})?',        # Rs. 1,299 / Rs 1,299
            r'INR\s*[\d,]+(?:\.\d{2})?',          # INR 1,299
            r'USD\s*[\d,]+(?:\.\d{2})?',          # USD 12.99
            r'€\s*[\d,]+(?:\.\d{2})?',            # €9.99
            r'MRP\s*�?\s*[\d,]+',                 # MRP 1,299
            r'(?<!\d)\d{2,4}(?:,\d{3})+(?:\.\d{2})?(?!\d)',  # 1,299 or 12,999.00
        ]
        
        price_matches = []
        for pattern in price_patterns:
            matches = re.finditer(pattern, html)
            for match in matches:
                price_matches.append({
                    'text': match.group(),
                    'start': match.start(),
                    'end': match.end()
                })
        
        logger.info(f"Found {len(price_matches)} price symbols. Scanning for product names...")
        
        if not price_matches:
            return []
        
        # Step 2: For each price, find nearby text that looks like a product name
        for price_info in price_matches[:15]:  # Limit to first 15 prices
            # Look 500 characters before the price for product names
            search_start = max(0, price_info['start'] - 500)
            search_end = price_info['start']
            nearby_text = html[search_start:search_end]
            
            # Remove HTML tags
            clean_text = BeautifulSoup(nearby_text, "html.parser").get_text()
            
            # Find text blocks that could be product names
            text_blocks = [t.strip() for t in re.split(r'\s{2,}|\n', clean_text) if len(t.strip()) > 10]
            
            # Score each text block
            best_match = None
            best_score = 0
            
            for text in text_blocks:
                score = self._score_product_name(text)
                if score > best_score:
                    best_score = score
                    best_match = text
            
            # If we found a good match
            if best_match and best_score > 50:
                # Try to find a link near this product
                link = self._find_link_near_price(html, price_info['start'], base_url)
                
                product = {
                    "name": best_match,
                    "price": price_info['text'],
                    "link": link,
                    "image_url": "N/A",
                    "specs": "N/A",
                    "healed": True  # Mark as self-healed
                }
                products.append(product)
        
        # Remove duplicates
        seen = set()
        unique_products = []
        for p in products:
            key = (p['name'], p['price'])
            if key not in seen:
                seen.add(key)
                unique_products.append(p)
        
        return unique_products[:20]
    
    def _score_product_name(self, text: str) -> int:
        """
        Score how likely this text is a product name (0-100)
        """
        score = 0
        
        # Good signs: reasonable length
        if 10 <= len(text) <= 150:
            score += 30
        
        # Bad signs: too short or too long
        if len(text) < 5 or len(text) > 200:
            score -= 50
        
        # Bad signs: contains menu/navigation words
        bad_words = ['home', 'menu', 'category', 'categories', 'sign in', 'login', 
                     'cart', 'search', 'filter', 'sort by', 'all rights reserved']
        if any(word in text.lower() for word in bad_words):
            score -= 40
        
        # Good signs: contains product-related words
        good_words = ['gb', 'tb', 'ram', 'processor', 'inch', 'laptop', 'phone', 
                      'camera', 'wireless', 'bluetooth', 'usb', 'hdmi']
        if any(word in text.lower() for word in good_words):
            score += 20
        
        # Good signs: has title case (proper nouns)
        if text[0].isupper() and not text.isupper():
            score += 15
        
        # Good signs: contains numbers (model numbers, specs)
        if re.search(r'\d', text):
            score += 10
        
        return max(0, score)
    
    def _find_link_near_price(self, html: str, price_position: int, base_url: str) -> str:
        """
        Find the nearest link to a price position
        """
        # Search in a window around the price
        search_start = max(0, price_position - 1000)
        search_end = min(len(html), price_position + 500)
        window = html[search_start:search_end]
        
        # Find all href attributes
        links = re.findall(r'href="([^"]+)"', window)
        
        for link in links:
            # Prefer links that look like product pages
            if any(keyword in link.lower() for keyword in ['/p/', '/product/', '/dp/', '/item/']):
                return urljoin(base_url, link)
        
        # Return first link if no product link found
        if links:
            return urljoin(base_url, links[0])

        return "N/A"

    def extract_with_llm(self, html: str, base_url: str, search_hint: str = "") -> List[Dict]:
        """
        Public wrapper for the 5th (LLM) strategy.

        Used by main.py AFTER the user confirms "yes, use AI mode" in the
        terminal. The auto-fallback in extract_data() still works as a
        safety net if this is never called.
        """
        if not html:
            return []
        hint = search_hint or self._guess_search_term(base_url)
        products = self.llm_healer.heal(html, hint)
        if not products:
            return []
        # Best-effort price cleanup, same as the other strategies.
        try:
            products = [self._validate_selling_price(p, html) for p in products]
            products = self._recover_prices_from_html(products, html)
        except Exception as e:
            logger.debug(f"LLMHealer: post-processing skipped due to: {e}")
        return products

    def _guess_search_term(self, base_url: str) -> str:
        """
        Best-effort search-term hint for the LLM healer.

        We pull the last meaningful chunk of the URL path. Examples:
          .../search?q=harry+potter+books  -> "harry potter books"
          .../catalog/electronics/laptops -> "laptops"

        Falls back to "products" if we can't figure anything out.
        Gemini still does the heavy lifting either way.
        """
        try:
            from urllib.parse import urlparse, unquote_plus, parse_qs
            parsed = urlparse(base_url)

            # 1. Prefer ?q= or ?s= or ?query= query strings
            qs = parse_qs(parsed.query)
            for key in ("q", "s", "query", "search", "searchTerm"):
                if key in qs and qs[key]:
                    return unquote_plus(qs[key][0]).replace("+", " ").strip()

            # 2. Otherwise use the last non-empty path segment
            parts = [p for p in parsed.path.split("/") if p]
            if parts:
                return unquote_plus(parts[-1]).replace("-", " ").replace("_", " ").strip()
        except Exception:
            pass
        return "products"