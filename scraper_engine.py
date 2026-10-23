"""
SCRAPER ENGINE
With TRUE Self-Healing: Fuzzy matching when all selectors fail
"""

import asyncio
import json
import logging
import random
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from antiban_engine import AntiBanEngine
from config import DELAY_BETWEEN_REQUESTS, PROXY_LIST
from llm_healer import LLMHealer

logger = logging.getLogger(__name__)


class ScraperEngine:
    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        self.antiban = AntiBanEngine(proxy_list=PROXY_LIST)
        self.llm_healer = LLMHealer()

    @staticmethod
    def _looks_binary(html: str) -> bool:
        if not html or len(html) < 100:
            return True
        sample = html[:5000]
        printable = sum(1 for c in sample if c.isprintable() or c in "\n\r\t ")
        ratio = printable / len(sample)
        return ratio < 0.6

    def _get_stealth_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        }

    # 🔥 PHASE 2: Added max_retries parameter for Fast-Fail Hybrid Fetching
    async def fetch_page(
        self, url: str, js_required: bool = False, max_retries: int = 3
    ) -> str | None:
        delay = random.uniform(*DELAY_BETWEEN_REQUESTS)
        await asyncio.sleep(delay)

        # Pass max_retries to the AntiBanEngine
        result = await self.antiban.fetch(
            url, use_browser=js_required, max_retries=max_retries
        )

        if result and result.get("success"):
            html_text = result.get("html")

            if self._looks_binary(html_text):
                logger.warning(
                    f"Response looks like binary data from AntiBanEngine for {url}"
                )
                return None

            content = html_text.lower()
            if any(
                block in content
                for block in [
                    "captcha",
                    "robot check",
                    "403 forbidden",
                    "access denied",
                ]
            ):
                logger.warning(
                    f"Bot detection triggered despite AntiBanEngine at {url}"
                )
                return None

            return html_text

        logger.error(
            f"AntiBanEngine failed to fetch {url}: {result.get('error') if result else 'Unknown error'}"
        )
        return None

    def extract_data(
        self, html: str, base_url: str, selectors: list[dict], regex_fallback: dict
    ) -> tuple[list[dict], dict]:
        soup = BeautifulSoup(html, "html.parser")

        # 1. JSON-LD structured data
        logger.info("Trying JSON-LD structured data extraction...")
        products = self._extract_from_jsonld(soup, base_url)
        if products:
            logger.info(f"✓ JSON-LD succeeded! Found {len(products)} products")
            products = [self._validate_selling_price(p, html) for p in products]
            products = self._recover_prices_from_html(products, html)
            return products, {"strategy_index": -3, "method": "json_ld"}

        # 🔥 PHASE 2: 1.5 Embedded JSON (Next.js / Shopify / Nuxt)
        logger.info("Trying Embedded JSON extraction...")
        products = self._extract_from_embedded_json(soup, base_url)
        if products:
            logger.info(f"✓ Embedded JSON succeeded! Found {len(products)} products")
            products = [self._validate_selling_price(p, html) for p in products]
            products = self._recover_prices_from_html(products, html)
            return products, {"strategy_index": -2.5, "method": "embedded_json"}

        # 2. CSS selectors
        for i, selector_set in enumerate(selectors):
            logger.info(f"Trying selector strategy {i + 1}/{len(selectors)}")
            products = self._extract_with_selectors(soup, base_url, selector_set)
            if products:
                logger.info(
                    f"✓ Strategy {i + 1} succeeded! Found {len(products)} products"
                )
                products = [self._validate_selling_price(p, html) for p in products]
                products = self._recover_prices_from_html(products, html)
                return products, {"strategy_index": i, "method": "css_selector"}
            logger.info(f"✗ Strategy {i + 1} found no products...")

        # 3. Regex fallback
        logger.warning("CSS failed. Trying regex fallback...")
        products = self._extract_with_regex(html, base_url, regex_fallback)
        if products:
            logger.info(f"✓ Regex succeeded! Found {len(products)} products")
            products = [self._validate_selling_price(p, html) for p in products]
            products = self._recover_prices_from_html(products, html)
            return products, {"strategy_index": -1, "method": "regex"}

        # 4. TRUE SELF-HEALING: Fuzzy matching
        logger.warning(
            "All traditional methods failed. Activating SELF-HEALING mode..."
        )
        products = self._self_heal_fuzzy_match(html, base_url)
        if products:
            logger.info(
                f"🧠 SELF-HEALING SUCCEEDED! Found {len(products)} products using intelligent matching"
            )
            products = [self._validate_selling_price(p, html) for p in products]
            products = self._recover_prices_from_html(products, html)
            return products, {"strategy_index": -2, "method": "self_healing"}

        # 5. LLM (Gemini) fallback
        logger.warning(
            "All 4 strategies failed. Activating LLM HEALER (Gemini) as last resort..."
        )
        search_hint = self._guess_search_term(base_url)
        products = self.llm_healer.heal(html, search_hint)
        if products:
            logger.info(
                f"🤖 LLM HEALER SUCCEEDED! Found {len(products)} product(s) via Gemini."
            )
            try:
                products = [self._validate_selling_price(p, html) for p in products]
                products = self._recover_prices_from_html(products, html)
            except Exception as e:
                logger.debug(f"LLMHealer: post-processing skipped due to: {e}")
            return products, {"strategy_index": -4, "method": "llm"}

        return [], {}

    def _extract_from_embedded_json(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[dict]:
        """Extract from Next.js, Nuxt, or Shopify embedded JSON blobs."""
        products = []
        try:
            scripts = soup.find_all("script", id=["__NEXT_DATA__", "__NUXT_DATA__"])
            for script in scripts:
                if not script.string:
                    continue
                data = json.loads(script.string)

                # Recursively walk the JSON tree to find lists of dictionaries that look like products
                def find_products(obj):
                    if isinstance(obj, list):
                        for item in obj:
                            if (
                                isinstance(item, dict)
                                and "name" in item
                                and ("price" in item or "offers" in item)
                            ):
                                p = self._parse_jsonld_product(item, base_url)
                                if p:
                                    products.append(p)
                            else:
                                find_products(item)
                    elif isinstance(obj, dict):
                        for val in obj.values():
                            find_products(val)

                find_products(data)
        except Exception as e:
            logger.debug(f"Embedded JSON parse error: {e}")
        return products

    def _recover_prices_from_html(self, products: list[dict], html: str) -> list[dict]:
        if not products or not html:
            return products

        price_patterns = [
            (r"₹\s*([\d,]+(?:\.\d{2})?)", "₹"),
            (r"Rs\.?\s*([\d,]+(?:\.\d{2})?)", "Rs"),
            (r"INR\s*([\d,]+(?:\.\d{2})?)", "INR"),
            (r"\$\s*([\d,]+(?:\.\d{2})?)", "$"),
        ]

        all_prices = []
        for pattern, symbol in price_patterns:
            for match in re.finditer(pattern, html):
                price_str = match.group(1).replace(",", "")
                try:
                    price_val = float(price_str)
                except ValueError:
                    continue

                context_start = max(0, match.start() - 200)
                context_end = min(len(html), match.end() + 50)
                context = html[context_start:context_end].lower()

                is_mrp = any(
                    marker in context
                    for marker in [
                        "strike",
                        "line-through",
                        "original",
                        "mrp",
                        "was",
                        "crossed",
                        "old-price",
                        "compare-at",
                        "list-price",
                        "_3auQ3N",
                        "_2pXp4L",
                    ]
                )

                all_prices.append(
                    {
                        "position": match.start(),
                        "price": price_str,
                        "price_val": price_val,
                        "symbol": symbol,
                        "full": match.group(0),
                        "is_mrp": is_mrp,
                    }
                )

        selling_prices = [p for p in all_prices if not p["is_mrp"]]
        logger.info(
            f"Price recovery: {len(all_prices)} total, {len(selling_prices)} are selling prices (not MRP)"
        )

        for product in products:
            if product.get("price") and product["price"] != "N/A":
                continue

            link = product.get("link", "")
            product_pos = -1

            if link and link != "N/A":
                if "/dp/" in link:
                    link_slug = link.split("/dp/")[1][:10]
                else:
                    link_slug = link.split("/")[-1].split("?")[0][:30] if link else ""

                if link_slug:
                    pos = html.find(link_slug)
                    if pos > 0:
                        product_pos = pos

            if product_pos < 0:
                try:
                    seq_idx = self._product_sequence_index(product, products)
                    if seq_idx < len(all_prices):
                        if seq_idx < len(selling_prices):
                            loc = selling_prices[seq_idx]
                        else:
                            loc = all_prices[seq_idx]
                        product["price"] = f"{loc['symbol']}{loc['price']}"
                        try:
                            product["price_float"] = float(loc["price"])
                        except ValueError:
                            pass
                        continue
                except ValueError:
                    continue

            closest_price = None
            min_distance = float("inf")
            search_window = 2000

            for loc in selling_prices:
                distance = abs(loc["position"] - product_pos)
                if distance < min_distance and distance < search_window:
                    min_distance = distance
                    closest_price = loc

            if not closest_price:
                for loc in all_prices:
                    distance = abs(loc["position"] - product_pos)
                    if distance < min_distance and distance < search_window:
                        min_distance = distance
                        closest_price = loc

            if closest_price:
                product["price"] = f"{closest_price['symbol']}{closest_price['price']}"
                try:
                    product["price_float"] = float(closest_price["price"])
                except ValueError:
                    pass

        return products

    def _validate_selling_price(self, product: dict, html: str) -> dict:
        price_str = product.get("price", "")
        if price_str == "N/A" or not price_str:
            return product

        price_float = product.get("price_float", 0)
        if not price_float or price_float < 100:
            return product

        link = product.get("link", "")
        if not link or link == "N/A":
            return product

        if "/dp/" in link:
            link_slug = link.split("/dp/")[1][:10]
        else:
            link_slug = link.split("/")[-1].split("?")[0][:30]

        product_pos = html.find(link_slug)
        if product_pos < 0:
            return product

        window_end = min(len(html), product_pos + 1500)
        window_html = html[product_pos:window_end]

        prices_in_window = []
        for match in re.finditer(r"₹\s*([\d,]+(?:\.\d{2})?)", window_html):
            price_val_str = match.group(1).replace(",", "")
            try:
                price_val = float(price_val_str)
                if price_val >= 100:
                    prices_in_window.append(price_val)
            except ValueError:
                continue

        if not prices_in_window:
            return product

        lowest = min(prices_in_window)
        if price_float > lowest * 1.05:
            product["price"] = f"₹{lowest:,.0f}"
            product["price_float"] = lowest

        return product

    def _extract_from_jsonld(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
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

                    item_type_raw = item.get("@type", "")
                    if isinstance(item_type_raw, list):
                        item_type = " ".join([str(t) for t in item_type_raw]).lower()
                    else:
                        item_type = str(item_type_raw).lower()

                    if "itemlist" in item_type:
                        for list_item in item.get("itemListElement", []):
                            if isinstance(list_item, dict):
                                nested = (
                                    list_item.get("listItem")
                                    or list_item.get("item")
                                    or list_item
                                )
                                if isinstance(nested, dict):
                                    p = self._parse_jsonld_product(nested, base_url)
                                    if p:
                                        products.append(p)
                        continue

                    if "product" not in item_type and "offer" not in item_type:
                        continue

                    product = self._parse_jsonld_product(item, base_url)
                    if product:
                        products.append(product)

        except Exception as e:
            logger.error(f"JSON-LD parse error: {e}")

        return products

    def _parse_jsonld_product(self, item: dict, base_url: str) -> dict | None:
        try:
            name = item.get("name", "").strip()
            if not name:
                return None

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

            if price is None:
                desc = item.get("description", "")
                m = re.search(r"[\d,]+\.?\d*", desc.replace(",", ""))
                if m:
                    price = m.group()

            price_str = "N/A"
            if price is not None:
                symbols = {"INR": "₹", "USD": "$", "GBP": "£", "EUR": "€"}
                sym = symbols.get(currency, "")
                price_str = f"{sym}{price}" if sym else f"{currency} {price}"

            link = item.get("url") or item.get("@id") or "N/A"
            if link != "N/A" and not link.startswith("http"):
                link = urljoin(base_url, link)

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

    def _safe_float(self, val) -> float | None:
        if val is None:
            return None
        try:
            return float(str(val).replace(",", ""))
        except (ValueError, TypeError):
            return None

    def _extract_with_selectors(
        self, soup: BeautifulSoup, base_url: str, selectors: dict
    ) -> list[dict]:
        products = []
        try:
            name_elements = soup.select(selectors["product_name"])
            if not name_elements:
                return []

            for name_elem in name_elements[:30]:
                product = {}
                name = name_elem.get_text(strip=True)

                a_tag = (
                    name_elem
                    if name_elem.name == "a"
                    else (name_elem.find_parent("a") or name_elem.find("a"))
                )

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

                image_url = self._extract_product_image(name_elem, base_url)
                product["image_url"] = image_url if image_url else "N/A"

                products.append(product)

        except Exception as e:
            logger.error(f"Selector error: {e}")
        return products

    def _find_nearby_price(self, name_elem, price_selector: str) -> str | None:
        if not price_selector:
            return None
        try:
            if "data-component-type" in name_elem.parent.attrs:
                container = name_elem.parent
            else:
                container = name_elem.find_parent(["div", "li", "article"])

            if container:
                price_elem = container.select_one(price_selector)
                if price_elem:
                    return price_elem.get_text(strip=True)

                parent_container = container.find_parent("div")
                if parent_container:
                    price_elem = parent_container.select_one(price_selector)
                    if price_elem:
                        return price_elem.get_text(strip=True)
        except Exception:
            pass
        return None

    def _find_nearby_specs(self, name_elem, specs_selector: str) -> str | None:
        if not specs_selector:
            return None
        try:
            container = name_elem.find_parent(["div", "li", "article"])
            if container:
                spec_elems = container.select(specs_selector)
                if spec_elems:
                    return " | ".join(e.get_text(strip=True) for e in spec_elems[:4])
        except Exception:
            pass
        return None

    def _extract_product_image(self, name_elem, base_url: str) -> str | None:
        try:
            for img in name_elem.find_all("img", recursive=True):
                src = (
                    img.get("data-src")
                    or img.get("src")
                    or img.get("data-lazy")
                    or img.get("data-original")
                )
                if src and src.startswith("data:"):
                    continue
                if src:
                    return urljoin(base_url, src)

            container = name_elem.find_parent(["div", "li", "article", "a"])
            if container:
                for img in container.find_all("img", recursive=True):
                    src = (
                        img.get("data-src")
                        or img.get("src")
                        or img.get("data-lazy")
                        or img.get("data-original")
                    )
                    if src and src.startswith("data:"):
                        continue
                    if src:
                        return urljoin(base_url, src)
        except Exception as e:
            logger.debug(f"Image extraction error: {e}")
        return None

    def _extract_with_regex(
        self, html: str, base_url: str, patterns: dict
    ) -> list[dict]:
        products = []
        try:
            name_pattern = patterns.get("product_name")
            if not name_pattern:
                return []

            name_matches = list(re.finditer(name_pattern, html))[:20]
            if not name_matches:
                return []

            price_pat = patterns.get("price")

            for nm in name_matches:
                name = nm.group(1) if nm.groups() else nm.group()
                if len(name) < 5:
                    continue

                win_start = max(0, nm.start() - 600)
                win_end = min(len(html), nm.end() + 200)
                window = html[win_start:win_end]
                name_mid = nm.start() - win_start

                price = "N/A"
                if price_pat:
                    best_pm = None
                    best_pd = float("inf")
                    for pm in re.finditer(price_pat, window):
                        pc = (pm.start() + pm.end()) / 2
                        d = abs(pc - name_mid)
                        if d < best_pd:
                            best_pd = d
                            best_pm = pm
                    if best_pm:
                        price = (
                            best_pm.group(1) if best_pm.groups() else best_pm.group()
                        )

                link = "N/A"
                href_matches = list(re.finditer(r'href="([^"]+)"', window))
                if href_matches:
                    best_lm = None
                    best_ld = float("inf")
                    for hm in href_matches:
                        url = hm.group(1)
                        url_pos = hm.start() + len('href="')
                        d = abs(url_pos - name_mid)
                        if d < best_ld:
                            best_ld = d
                            best_lm = url
                    if best_lm:
                        link = urljoin(base_url, best_lm)

                products.append(
                    {
                        "name": name,
                        "price": price,
                        "link": link,
                        "image_url": "N/A",
                        "specs": "N/A",
                    }
                )
        except Exception as e:
            logger.error(f"Regex error: {e}")
        return products

    def _self_heal_fuzzy_match(self, html: str, base_url: str) -> list[dict]:
        products = []

        price_patterns = [
            r"₹\s*[\d,]+(?:\.\d{2})?",
            r"\$\s*[\d,]+(?:\.\d{2})?",
            r"£\s*[\d,]+(?:\.\d{2})?",
            r"Rs\.?\s*[\d,]+(?:\.\d{2})?",
            r"INR\s*[\d,]+(?:\.\d{2})?",
            r"USD\s*[\d,]+(?:\.\d{2})?",
            r"€\s*[\d,]+(?:\.\d{2})?",
            r"MRP\s*�?\s*[\d,]+",
            r"(?<!\d)\d{2,4}(?:,\d{3})+(?:\.\d{2})?(?!\d)",
        ]

        price_matches = []
        for pattern in price_patterns:
            matches = re.finditer(pattern, html)
            for match in matches:
                price_matches.append(
                    {"text": match.group(), "start": match.start(), "end": match.end()}
                )

        logger.info(
            f"Found {len(price_matches)} price symbols. Scanning for product names..."
        )

        if not price_matches:
            return []

        for price_info in price_matches[:15]:
            search_start = max(0, price_info["start"] - 500)
            search_end = price_info["start"]
            nearby_text = html[search_start:search_end]

            clean_text = BeautifulSoup(nearby_text, "html.parser").get_text()
            text_blocks = [
                t.strip()
                for t in re.split(r"\s{2,}|\n", clean_text)
                if len(t.strip()) > 10
            ]

            best_match = None
            best_score = 0

            for text in text_blocks:
                score = self._score_product_name(text)
                if score > best_score:
                    best_score = score
                    best_match = text

            if best_match and best_score > 50:
                name_pos = price_info["start"] - 300
                link = self._find_link_near_price(
                    html, price_info["start"], base_url, name_position=name_pos
                )

                product = {
                    "name": best_match,
                    "price": price_info["text"],
                    "link": link,
                    "image_url": "N/A",
                    "specs": "N/A",
                    "healed": True,
                }
                products.append(product)

        seen = set()
        unique_products = []
        for p in products:
            key = (p["name"], p["price"])
            if key not in seen:
                seen.add(key)
                unique_products.append(p)

        return unique_products[:20]

    def _score_product_name(self, text: str) -> int:
        score = 0
        if 10 <= len(text) <= 150:
            score += 30
        if len(text) < 5 or len(text) > 200:
            score -= 50
        bad_words = [
            "home",
            "menu",
            "category",
            "categories",
            "sign in",
            "login",
            "cart",
            "search",
            "filter",
            "sort by",
            "all rights reserved",
        ]
        if any(word in text.lower() for word in bad_words):
            score -= 40
        good_words = [
            "gb",
            "tb",
            "ram",
            "processor",
            "inch",
            "laptop",
            "phone",
            "camera",
            "wireless",
            "bluetooth",
            "usb",
            "hdmi",
        ]
        if any(word in text.lower() for word in good_words):
            score += 20
        if text[0].isupper() and not text.isupper():
            score += 15
        if re.search(r"\d", text):
            score += 10
        return max(0, score)

    def _product_sequence_index(self, product: dict, products: list[dict]) -> int:
        for i, p in enumerate(products):
            if (p.get("name"), p.get("price"), p.get("link")) == (
                product.get("name"),
                product.get("price"),
                product.get("link"),
            ):
                return i
        return -1

    def _find_link_near_price(
        self, html: str, price_position: int, base_url: str, name_position: int = None
    ) -> str:
        anchor = name_position if name_position is not None else price_position
        search_start = max(0, anchor - 800)
        search_end = min(len(html), anchor + 800)
        window = html[search_start:search_end]

        href_matches = list(re.finditer(r'href="([^"]+)"', window))
        if not href_matches:
            return "N/A"

        product_path_hints = (
            "/dp/",
            "/product/",
            "/p/",
            "/item/",
            "/buy/",
            "/offer/",
            "/deals/",
            "/shop/",
        )
        best_product = None
        best_any = None
        best_any_dist = float("inf")

        for hm in href_matches:
            url = hm.group(1)
            url_pos = hm.start() + len('href="')
            dist = abs(url_pos - anchor)
            if dist < best_any_dist:
                best_any_dist = dist
                best_any = url
            if any(hint in url.lower() for hint in product_path_hints):
                if best_product is None or dist < best_product[0]:
                    best_product = (dist, url)

        if best_product:
            return urljoin(base_url, best_product[1])
        return urljoin(base_url, best_any) if best_any else "N/A"

    def extract_with_llm(
        self, html: str, base_url: str, search_hint: str = ""
    ) -> list[dict]:
        if not html:
            return []
        hint = search_hint or self._guess_search_term(base_url)
        products = self.llm_healer.heal(html, hint)
        if not products:
            return []
        try:
            products = [self._validate_selling_price(p, html) for p in products]
            products = self._recover_prices_from_html(products, html)
        except Exception as e:
            logger.debug(f"LLMHealer: post-processing skipped due to: {e}")
        return products

    def _guess_search_term(self, base_url: str) -> str:
        try:
            parsed = urlparse(base_url)
            from urllib.parse import parse_qs, unquote_plus

            qs = parse_qs(parsed.query)
            for key in ("q", "s", "query", "search", "searchTerm"):
                if qs.get(key):
                    return unquote_plus(qs[key][0]).replace("+", " ").strip()

            parts = [p for p in parsed.path.split("/") if p]
            if parts:
                return (
                    unquote_plus(parts[-1]).replace("-", " ").replace("_", " ").strip()
                )
        except Exception:
            pass
        return "products"

    def get_session_headers(self, domain: str = None) -> dict[str, str]:
        base_headers = self._get_stealth_headers()
        if domain:
            base_headers["Referer"] = f"https://{domain}/"
            base_headers["Origin"] = f"https://{domain}"
        return base_headers
