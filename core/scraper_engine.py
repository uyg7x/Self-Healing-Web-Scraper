import json
import logging
import re
from urllib.parse import urljoin, urlparse, parse_qs, unquote_plus

from bs4 import BeautifulSoup

from ai.llm_healer import LLMHealer

logger = logging.getLogger(__name__)


class ScraperEngine:
    def __init__(self, ai_backends: set[str] | None = None):
        self.ai_backends = ai_backends if ai_backends is not None else {"gemini", "qwen"}
        self.llm_healer = LLMHealer()
        self.llm_healer.runtime_enabled = "gemini" in self.ai_backends

    @staticmethod
    def _looks_binary(html: str) -> bool:
        if not html or len(html) < 100:
            return True
        sample = html[:5000]
        printable = sum(1 for c in sample if c.isprintable() or c in "\n\r\t ")
        return (printable / len(sample)) < 0.6


    def extract_data(
        self, html: str, base_url: str, selectors: list[dict], regex_fallback: dict,
        site_key: str | None = None,
    ) -> tuple[list[dict], dict]:
        if self._looks_binary(html):
            return [], {}


        if site_key == "alibaba":
            products = self._extract_alibaba(html, base_url)
            if products:
                products = self._recover_prices_from_html(products, html)
                return products, {"strategy_index": -14, "method": "alibaba_parser"}


        if site_key == "ebay":
            products = self._extract_ebay(html, base_url)
            if products:
                products = self._recover_prices_from_html(products, html)
                return products, {"strategy_index": -10, "method": "ebay_parser"}

        if site_key == "newegg":
            products = self._extract_newegg(html, base_url)
            if products:
                products = self._recover_prices_from_html(products, html)
                return products, {"strategy_index": -11, "method": "newegg_parser"}

        if site_key == "temu":
            products = self._extract_temu(html, base_url)
            if products:
                products = self._recover_prices_from_html(products, html)
                return products, {"strategy_index": -12, "method": "temu_parser"}

  
        soup = BeautifulSoup(html, "html.parser")

        products = self._extract_from_jsonld(soup, base_url)
        if products:
            products = [self._validate_selling_price(p, html) for p in products]
            products = self._recover_prices_from_html(products, html)
            return products, {"strategy_index": -3, "method": "json_ld"}

        products = self._extract_from_embedded_json(soup, base_url)
        if products:
            products = [self._validate_selling_price(p, html) for p in products]
            products = self._recover_prices_from_html(products, html)
            return products, {"strategy_index": -2.5, "method": "embedded_json"}

        for i, selector_set in enumerate(selectors):
            products = self._extract_with_selectors(soup, base_url, selector_set)
            if products:
                products = [self._validate_selling_price(p, html) for p in products]
                products = self._recover_prices_from_html(products, html)
                return products, {"strategy_index": i, "method": "css_selector"}

        products = self._extract_with_regex(html, base_url, regex_fallback)
        if products:
            products = [self._validate_selling_price(p, html) for p in products]
            products = self._recover_prices_from_html(products, html)
            return products, {"strategy_index": -1, "method": "regex"}

        products = self._self_heal_fuzzy_match(html, base_url)
        if products:
            products = [self._validate_selling_price(p, html) for p in products]
            products = self._recover_prices_from_html(products, html)
            return products, {"strategy_index": -2, "method": "self_healing"}

        search_hint = self._guess_search_term(base_url)
        products = self.llm_healer.heal(html, search_hint)
        if products:
            try:
                products = [self._validate_selling_price(p, html) for p in products]
                products = self._recover_prices_from_html(products, html)
            except Exception:
                pass
            return products, {"strategy_index": -4, "method": "llm"}

        return [], {}


    def _extract_alibaba(self, html: str, base_url: str) -> list[dict]:
      
        challenge_markers = ("punish-component", "awsc.js", "baxia-punish")
        if any(m in html for m in challenge_markers):
            logger.warning("[alibaba] challenge page detected - no products extracted")
            return []

  
        products = self._extract_alibaba_json(html, base_url)
        if products:
            logger.info(f"[alibaba] embedded JSON: {len(products)} items")
            return products

  
        soup = BeautifulSoup(html, "html.parser")

        card_selectors = (
            "div[data-spm='normal_offer']",
            ".search-card-item",
            "div.fy23-search-card",
        )

        for card_sel in card_selectors:
            cards = soup.select(card_sel)
            if not cards:
                continue

            logger.info(f"[alibaba] CSS {card_sel}: {len(cards)} cards")
            for card in cards:
                title_el = (
                    card.select_one("h2")
                    or card.select_one(".search-card-e-title")
                    or card.select_one("[class*='title']")
                )
                if not title_el:
                    continue
                name = title_el.get_text(" ", strip=True)
                if not name or len(name) < 8:
                    continue

                link_el = (
                    card.select_one("a[href*='product-detail']")
                    or card.select_one("a[href*='offer']")
                    or card.select_one("a[href]")
                )
                href = link_el.get("href", "") if link_el else ""
                link = href if href.startswith("http") else urljoin(base_url, href)

                price_el = (
                    card.select_one(".search-card-e-price-main")
                    or card.select_one("[class*='price']")
                )
                price_raw = price_el.get_text(" ", strip=True) if price_el else "N/A"
                price_float = self._safe_float(
                    re.sub(r"[^\d.]", "", price_raw.split("-")[0])
                    if price_raw != "N/A" else None
                )

                specs_el = card.select(
                    ".search-card-m-sale-features__item, .search-card-e-company"
                )
                specs = (
                    " | ".join(e.get_text(" ", strip=True) for e in specs_el[:4])
                    if specs_el else "N/A"
                )

                img_el = card.select_one("img")
                image = ""
                if img_el:
                    src = img_el.get("data-src") or img_el.get("src") or ""
                    if src and not src.startswith("data:"):
                        image = urljoin(base_url, src)

                products.append({
                    "name": name,
                    "price": price_raw,
                    "price_float": price_float,
                    "link": link or "N/A",
                    "image_url": image or "N/A",
                    "specs": specs,
                })

            if products:
                return products

        return products

    def _extract_alibaba_json(self, html: str, base_url: str) -> list[dict]:
       
        marker_re = re.compile(
            r"window\.__page__data\w*\.\w*[Oo]ffer\w*\s*=\s*(\{)",
            re.DOTALL,
        )
        m = marker_re.search(html)
        if not m:
          
            m = re.search(
                r"window\.__page__data\s*=\s*(\{)",
                html, re.DOTALL,
            )
        if not m:
            return []

        start = m.start(1)
        depth = 0
        end = start
        for i in range(start, min(len(html), start + 5_000_000)):
            ch = html[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        if end <= start:
            return []

        blob = html[start:end]
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            return []


        offers = (
            data.get("_offer_list")
            or data.get("offerList")
            or data.get("offers")
        )
        if not offers:
            offers = self._find_offer_list(data)

        if not offers:
            return []

        products = []
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            name = (
                offer.get("subject")
                or offer.get("title")
                or offer.get("productTitle")
            )
            if not name or not isinstance(name, str) or len(name) < 8:
                continue

            price = (
                offer.get("price")
                or offer.get("salePrice")
                or offer.get("priceRange")
            )
            pf = None
            if isinstance(price, (int, float)):
                pf = float(price)
            elif isinstance(price, str):
                pf = self._safe_float(re.sub(r"[^\d.]", "", price.split("-")[0]))

            url = (
                offer.get("productUrl")
                or offer.get("detailUrl")
                or offer.get("url")
            )
            link = url or "N/A"
            if link != "N/A" and not link.startswith("http"):
                link = urljoin(base_url, link)

            image = offer.get("imageUrl") or offer.get("image") or "N/A"
            if isinstance(image, str) and image.startswith("//"):
                image = "https:" + image

            specs_parts = []
            if offer.get("companyName"):
                specs_parts.append(str(offer["companyName"]))
            if offer.get("moq") or offer.get("minOrder"):
                specs_parts.append(f"MOQ {offer.get('moq') or offer.get('minOrder')}")

            products.append({
                "name": name,
                "price": str(price or "N/A"),
                "price_float": pf,
                "link": link,
                "image_url": image if isinstance(image, str) else "N/A",
                "specs": " | ".join(specs_parts) if specs_parts else "N/A",
            })

        return products

    def _find_offer_list(self, obj, depth=0):
      
        if depth > 8:
            return None
        best = None
        best_len = 0
        stack = [obj]
        visited = 0
        while stack and visited < 5000:
            cur = stack.pop(0)
            visited += 1
            if isinstance(cur, list):
                if cur and isinstance(cur[0], dict) and any(
                    k in cur[0] for k in ("subject", "productId", "offerId")
                ):
                    if len(cur) > best_len:
                        best, best_len = cur, len(cur)
                else:
                    stack.extend(cur[:50])
            elif isinstance(cur, dict):
                stack.extend(list(cur.values())[:50])
        return best

  
    def _extract_ebay(self, html: str, base_url: str) -> list[dict]:
        products = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            cards = (
                soup.select("li.s-card")
                or soup.select("li.s-item")
                or soup.select(".srp-results li[data-listingid]")
            )
            for card in cards:
                title_el = (
                    card.select_one(".s-card__title")
                    or card.select_one(".s-item__title")
                    or card.select_one("h3")
                )
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if not title or "Shop on eBay" in title:
                    continue

                link_el = (
                    card.select_one("a.s-card__link")
                    or card.select_one("a.s-item__link")
                    or card.select_one("a[href*='ebay.com/itm']")
                )
                href = link_el.get("href", "") if link_el else ""
                link = href if href.startswith("http") else urljoin(base_url, href)

                price_el = (
                    card.select_one(".s-card__price")
                    or card.select_one("span.s-item__price")
                    or card.select_one("[class*='price']")
                )
                price_raw = price_el.get_text(strip=True) if price_el else "N/A"
                price_float = self._safe_float(
                    re.sub(r"[^\d.]", "", price_raw.split()[0])
                    if price_raw != "N/A" and price_raw.split() else None
                )

                img_el = card.select_one("img.s-card__image") or card.select_one("img")
                image = ""
                if img_el:
                    src = img_el.get("data-src") or img_el.get("src") or ""
                    if src and not src.startswith("data:"):
                        image = urljoin(base_url, src)

                products.append({
                    "name": title,
                    "price": price_raw,
                    "price_float": price_float,
                    "link": link or "N/A",
                    "image_url": image or "N/A",
                    "specs": "N/A",
                })
        except Exception as e:
            logger.error(f"eBay extractor error: {e}")
        return products


    def _extract_newegg(self, html: str, base_url: str) -> list[dict]:
        products = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            for cell in soup.select(".item-cell"):
                name_el = cell.select_one(".item-title")
                if not name_el:
                    continue
                name = name_el.get_text(strip=True)
                if not name or len(name) < 10:
                    continue

                link = "N/A"
                if name_el.name == "a" and name_el.get("href"):
                    link = urljoin(base_url, name_el["href"])
                else:
                    a = name_el.find_parent("a") or name_el.find("a")
                    if a and a.get("href"):
                        link = urljoin(base_url, a["href"])

                price_el = cell.select_one(".price-current")
                price_raw = price_el.get_text(strip=True) if price_el else "N/A"
                price_float = self._safe_float(
                    re.sub(r"[^\d.]", "", price_raw) if price_raw != "N/A" else None
                )

                specs = ""
                feature_lis = cell.select(".item-features li")
                if feature_lis:
                    specs = " | ".join(
                        li.get_text(" ", strip=True) for li in feature_lis[:5]
                    )

                img_el = cell.select_one("img")
                image = ""
                if img_el:
                    src = img_el.get("data-src") or img_el.get("src") or ""
                    if src and not src.startswith("data:"):
                        image = urljoin(base_url, src)

                products.append({
                    "name": name,
                    "price": price_raw,
                    "price_float": price_float,
                    "link": link,
                    "image_url": image or "N/A",
                    "specs": specs or "N/A",
                })
        except Exception as e:
            logger.error(f"Newegg extractor error: {e}")
        return products


    def _extract_temu(self, html: str, base_url: str) -> list[dict]:
        products = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            cards = (
                soup.select("div[data-uniqid]")
                or soup.select("div[class*='product-card']")
                or soup.select("a[href*='goods.html']")
            )
            for card in cards:
                title_el = (
                    card.select_one("a[class*='title']")
                    or card.select_one("[class*='title']")
                    or card.select_one("h3")
                )
                if not title_el:
                    continue
                name = title_el.get_text(strip=True)
                if not name or len(name) < 8:
                    continue

                link_el = card.select_one("a[href]") or card
                href = ""
                if hasattr(link_el, "get"):
                    href = link_el.get("href", "") or ""
                link = href if href.startswith("http") else urljoin(base_url, href)

                price_el = (
                    card.select_one("span[class*='price']")
                    or card.select_one("[class*='price']")
                )
                price_raw = price_el.get_text(strip=True) if price_el else "N/A"
                price_float = self._safe_float(
                    re.sub(r"[^\d.]", "", price_raw) if price_raw != "N/A" else None
                )

                img_el = card.select_one("img")
                image = ""
                if img_el:
                    src = img_el.get("data-src") or img_el.get("src") or ""
                    if src and not src.startswith("data:"):
                        image = urljoin(base_url, src)

                products.append({
                    "name": name,
                    "price": price_raw,
                    "price_float": price_float,
                    "link": link or "N/A",
                    "image_url": image or "N/A",
                    "specs": "N/A",
                })
        except Exception as e:
            logger.error(f"Temu extractor error: {e}")
        return products


    def _extract_from_jsonld(self, soup, base_url):
        products = []
        try:
            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                try:
                    data = json.loads(script.string or "{}")
                except (json.JSONDecodeError, TypeError):
                    continue
                items = []
                if isinstance(data, dict):
                    items = data["@graph"] if "@graph" in data else [data]
                elif isinstance(data, list):
                    items = data
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    raw = item.get("@type", "")
                    if isinstance(raw, list):
                        item_type = " ".join(str(t) for t in raw).lower()
                    else:
                        item_type = str(raw).lower()
                    if "itemlist" in item_type:
                        for li in item.get("itemListElement", []):
                            if isinstance(li, dict):
                                nested = li.get("listItem") or li.get("item") or li
                                if isinstance(nested, dict):
                                    p = self._parse_jsonld_product(nested, base_url)
                                    if p:
                                        products.append(p)
                        continue
                    if "product" not in item_type and "offer" not in item_type:
                        continue
                    p = self._parse_jsonld_product(item, base_url)
                    if p:
                        products.append(p)
        except Exception as e:
            logger.error(f"JSON-LD error: {e}")
        return products

    def _parse_jsonld_product(self, item, base_url):
        try:
            name = (item.get("name") or "").strip()
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
            price_str = "N/A"
            if price is not None:
                syms = {"INR": "₹", "USD": "$", "GBP": "£", "EUR": "€"}
                sym = syms.get(currency, "")
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
        except Exception:
            return None


    def _extract_from_embedded_json(self, soup, base_url):
        products = []
        try:
            scripts = soup.find_all("script", id=["__NEXT_DATA__", "__NUXT_DATA__"])
            for script in scripts:
                if not script.string:
                    continue
                data = json.loads(script.string)

                def walk(obj):
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
                                walk(item)
                    elif isinstance(obj, dict):
                        for v in obj.values():
                            walk(v)

                walk(data)
        except Exception as e:
            logger.debug(f"Embedded JSON error: {e}")
        return products


    def _extract_with_selectors(self, soup, base_url, selectors):
        products = []
        try:
            name_elems = soup.select(selectors["product_name"])
            for name_elem in name_elems[:40]:
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
                link = (
                    urljoin(base_url, a_tag["href"])
                    if a_tag and a_tag.get("href")
                    else "N/A"
                )
                price = self._find_nearby_price(name_elem, selectors.get("price"))
                specs = self._find_nearby_specs(name_elem, selectors.get("specs"))
                image_url = self._extract_product_image(name_elem, base_url)
                products.append({
                    "name": name,
                    "price": price or "N/A",
                    "link": link,
                    "image_url": image_url or "N/A",
                    "specs": specs or "N/A",
                })
        except Exception as e:
            logger.error(f"Selector error: {e}")
        return products

    def _find_nearby_price(self, name_elem, price_selector):
        if not price_selector:
            return None
        try:
            container = (
                name_elem.parent
                if "data-component-type" in name_elem.parent.attrs
                else name_elem.find_parent(["div", "li", "article"])
            )
            if container:
                pe = container.select_one(price_selector)
                if pe:
                    return pe.get_text(strip=True)
                parent = container.find_parent("div")
                if parent:
                    pe = parent.select_one(price_selector)
                    if pe:
                        return pe.get_text(strip=True)
        except Exception:
            pass
        return None

    def _find_nearby_specs(self, name_elem, specs_selector: str) -> str | None:
        if not specs_selector:
            return None
        try:
            container = None
            node = name_elem
            for _ in range(10):
                node = node.parent
                if node is None:
                    break
                if node.get("data-component-type") == "s-search-result":
                    container = node
                    break
                classes = node.get("class") or []
                classes_lower = " ".join(classes).lower() if classes else ""
                if any(k in classes_lower for k in ("product", "card", "result", "grid")):
                    container = node
                    if node.parent and node.parent.get("data-component-type"):
                        container = node.parent
                    break
            if container is None:
                container = name_elem.find_parent(["div", "li", "article"])
            if not container:
                return None
            spec_elems = container.select(specs_selector)
            if not spec_elems:
                return None
            junk = (
                "out of 5 stars", "stars", "ratings", "reviews", "rated",
                "prime", "sponsored", "free delivery", "delivery by",
                "coupon", "save ", "% off", "more buying choices",
                "bank offer", "emi", "cashback", "no cost",
            )
            collected = []
            seen = set()
            for e in spec_elems:
                txt = e.get_text(" ", strip=True)
                if not txt or len(txt) < 3:
                    continue
                low = txt.lower()
                if any(j in low for j in junk):
                    continue
                if low in seen:
                    continue
                seen.add(low)
                collected.append(txt)
                if len(collected) >= 8:
                    break
            if collected:
                return " | ".join(collected)
        except Exception as e:
            logger.debug(f"Specs extraction error: {e}")
        return None

    def _extract_product_image(self, name_elem, base_url):
        try:
            for img in name_elem.find_all("img", recursive=True):
                src = (
                    img.get("data-src")
                    or img.get("src")
                    or img.get("data-lazy")
                    or img.get("data-original")
                )
                if src and not src.startswith("data:"):
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
                    if src and not src.startswith("data:"):
                        return urljoin(base_url, src)
        except Exception:
            pass
        return None



    def _extract_with_regex(self, html, base_url, patterns):
        products = []
        try:
            name_pattern = patterns.get("product_name")
            if not name_pattern:
                return []
            name_matches = list(re.finditer(name_pattern, html))[:25]
            price_pat = patterns.get("price")
            for nm in name_matches:
                name = nm.group(1) if nm.groups() else nm.group()
                if len(name) < 5:
                    continue
                win_start = max(0, nm.start() - 600)
                window = html[win_start: min(len(html), nm.end() + 200)]
                mid = nm.start() - win_start
                price = "N/A"
                if price_pat:
                    best_pm, best_pd = None, float("inf")
                    for pm in re.finditer(price_pat, window):
                        pc = (pm.start() + pm.end()) / 2
                        d = abs(pc - mid)
                        if d < best_pd:
                            best_pd, best_pm = d, pm
                    if best_pm:
                        price = best_pm.group(1) if best_pm.groups() else best_pm.group()
                link = "N/A"
                hrefs = list(re.finditer(r'href="([^"]+)"', window))
                if hrefs:
                    best_lm, best_ld = None, float("inf")
                    for hm in hrefs:
                        d = abs(hm.start() + len('href="') - mid)
                        if d < best_ld:
                            best_ld, best_lm = d, hm.group(1)
                    if best_lm:
                        link = urljoin(base_url, best_lm)
                products.append({
                    "name": name,
                    "price": price,
                    "link": link,
                    "image_url": "N/A",
                    "specs": "N/A",
                })
        except Exception as e:
            logger.error(f"Regex error: {e}")
        return products



    def _self_heal_fuzzy_match(self, html, base_url):
        products = []
        pats = [
            r"₹\s*[\d,]+(?:\.\d{2})?",
            r"\$\s*[\d,]+(?:\.\d{2})?",
            r"£\s*[\d,]+(?:\.\d{2})?",
            r"Rs\.?\s*[\d,]+(?:\.\d{2})?",
        ]
        matches = []
        for pat in pats:
            for m in re.finditer(pat, html):
                matches.append({"text": m.group(), "start": m.start()})
        if not matches:
            return []
        for price in matches[:20]:
            window = html[max(0, price["start"] - 500): price["start"]]
            clean = BeautifulSoup(window, "html.parser").get_text()
            blocks = [
                t.strip()
                for t in re.split(r"\s{2,}|\n", clean)
                if len(t.strip()) > 10
            ]
            best, best_score = None, 0
            for block in blocks:
                score = self._score_name(block)
                if score > best_score:
                    best_score, best = score, block
            if best and best_score > 50:
                link = self._find_link_near(
                    html, price["start"], base_url, price["start"] - 300
                )
                products.append({
                    "name": best,
                    "price": price["text"],
                    "link": link,
                    "image_url": "N/A",
                    "specs": "N/A",
                    "healed": True,
                })
        seen, out = set(), []
        for p in products:
            key = (p["name"], p["price"])
            if key not in seen:
                seen.add(key)
                out.append(p)
        return out[:20]

    def _score_name(self, text):
        score = 0
        if 10 <= len(text) <= 150:
            score += 30
        if len(text) < 5 or len(text) > 200:
            score -= 50
        for bad in (
            "home", "menu", "category", "sign in", "login", "cart",
            "search", "filter", "sort by", "all rights reserved",
        ):
            if bad in text.lower():
                score -= 40
                break
        for good in (
            "gb", "tb", "ram", "processor", "inch", "laptop",
            "phone", "camera", "wireless", "bluetooth", "usb", "hdmi",
        ):
            if good in text.lower():
                score += 20
                break
        if text[:1].isupper() and not text.isupper():
            score += 15
        if re.search(r"\d", text):
            score += 10
        return max(0, score)

    def _find_link_near(self, html, price_pos, base_url, name_pos=None):
        anchor = name_pos if name_pos is not None else price_pos
        window = html[max(0, anchor - 800): min(len(html), anchor + 800)]
        hrefs = list(re.finditer(r'href="([^"]+)"', window))
        if not hrefs:
            return "N/A"
        hints = ("/dp/", "/product/", "/p/", "/item/", "/buy/")
        best_prod, best_any, best_d = None, None, float("inf")
        for hm in hrefs:
            url = hm.group(1)
            d = abs(hm.start() + len('href="') - anchor)
            if d < best_d:
                best_d, best_any = d, url
            if any(h in url.lower() for h in hints):
                if best_prod is None or d < best_prod[0]:
                    best_prod = (d, url)
        if best_prod:
            return urljoin(base_url, best_prod[1])
        return urljoin(base_url, best_any) if best_any else "N/A"


    def _validate_selling_price(self, product, html):
        price_str = product.get("price", "")
        pf = product.get("price_float", 0)
        if not price_str or price_str == "N/A" or not pf or pf < 100:
            return product
        link = product.get("link", "")
        if not link or link == "N/A":
            return product
        slug = (
            link.split("/dp/")[1][:10]
            if "/dp/" in link
            else link.split("/")[-1].split("?")[0][:30]
        )
        pos = html.find(slug)
        if pos < 0:
            return product
        window = html[pos: min(len(html), pos + 1500)]
        prices = []
        for m in re.finditer(r"₹\s*([\d,]+(?:\.\d{2})?)", window):
            try:
                v = float(m.group(1).replace(",", ""))
                if v >= 100:
                    prices.append(v)
            except ValueError:
                continue
        if prices:
            lowest = min(prices)
            if pf > lowest * 1.05:
                product["price"] = f"₹{lowest:,.0f}"
                product["price_float"] = lowest
        return product

    def _recover_prices_from_html(self, products, html):
        if not products or not html:
            return products
        symbols = [
            (r"₹\s*([\d,]+(?:\.\d{2})?)", "₹"),
            (r"Rs\.?\s*([\d,]+(?:\.\d{2})?)", "Rs"),
            (r"INR\s*([\d,]+(?:\.\d{2})?)", "INR"),
            (r"\$\s*([\d,]+(?:\.\d{2})?)", "$"),
            (r"£\s*([\d,]+(?:\.\d{2})?)", "£"),
            (r"€\s*([\d,]+(?:\.\d{2})?)", "€"),
        ]
        all_prices = []
        for pat, sym in symbols:
            for m in re.finditer(pat, html):
                try:
                    val = float(m.group(1).replace(",", ""))
                except ValueError:
                    continue
                ctx = html[
                    max(0, m.start() - 200): min(len(html), m.end() + 50)
                ].lower()
                is_mrp = any(
                    mk in ctx
                    for mk in (
                        "strike", "line-through", "original", "mrp", "was",
                        "crossed", "old-price", "compare-at", "list-price",
                    )
                )
                all_prices.append({
                    "pos": m.start(),
                    "price": m.group(1),
                    "symbol": sym,
                    "is_mrp": is_mrp,
                })
        selling = [p for p in all_prices if not p["is_mrp"]]
        for product in products:
            if product.get("price") and product["price"] != "N/A":
                continue
            link = product.get("link", "")
            if not link or link == "N/A":
                continue
            slug = (
                link.split("/dp/")[1][:10]
                if "/dp/" in link
                else link.split("/")[-1].split("?")[0][:30]
            )
            pos = html.find(slug)
            if pos < 0:
                continue
            closest, best_d = None, float("inf")
            for loc in selling or all_prices:
                d = abs(loc["pos"] - pos)
                if d < best_d and d < 2000:
                    best_d, closest = d, loc
            if closest:
                product["price"] = f"{closest['symbol']}{closest['price']}"
                try:
                    product["price_float"] = float(
                        closest["price"].replace(",", "")
                    )
                except ValueError:
                    pass
        return products

    @staticmethod
    def _safe_float(val):
        if val is None:
            return None
        try:
            return float(str(val).replace(",", ""))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _guess_search_term(base_url):
        try:
            parsed = urlparse(base_url)
            qs = parse_qs(parsed.query)
            for k in ("q", "s", "query", "search", "searchTerm", "SearchText"):
                if qs.get(k):
                    return unquote_plus(qs[k][0]).replace("+", " ").strip()
            parts = [p for p in parsed.path.split("/") if p]
            if parts:
                return (
                    unquote_plus(parts[-1])
                    .replace("-", " ")
                    .replace("_", " ")
                    .strip()
                )
        except Exception:
            pass
        return "products"
