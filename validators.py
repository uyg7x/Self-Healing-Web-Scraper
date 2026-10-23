# ============================================================
# validators.py - Data validation, garbage filtering & relevance scoring
# ============================================================

import logging
import re
from difflib import SequenceMatcher

from config import VALIDATION_RULES
from schemas import ProductSchema  # 🔥 PHASE 4: Import Pydantic schema

logger = logging.getLogger(__name__)

GARBAGE_WORDS = {
    "home",
    "men",
    "women",
    "categories",
    "clothing",
    "footwear",
    "accessories",
    "mobiles",
    "electronics",
    "toys and games",
    "bags, wallets & belts",
    "electronic kits",
    "science project kit",
    "search for products",
    "search for products, brands and more",
    "all categories",
    "all that's new",
    "new arrivals",
    "best sellers",
    "home decor",
    "6 gb",
    "8 gb",
    "4 gb",
    "3 gb",
    "50% or more",
    "40% or more",
    "30% or more",
    "20% or more",
    "10% or more",
    "1 gb",
    "2 gb",
    "special price",
    "buying guide",
    "myntra",
    "shops",
    "cleartrip",
    "buy more, save more",
    "check each product page",
    "add to cart",
    "view all",
    "see more",
    "show more",
    "load more",
    "filter by",
    "sort by",
    "price low to high",
    "price high to low",
    "plus size",
    "grooming",
    "winterwear",
    "night & loungewear",
    "ajio global",
    "poco",
    "flipkart",
    "amazon",
    "meesho",
    "all",
    "new",
    "sale",
    "offers",
    "deals",
    "trending",
    "popular",
    "featured",
    "recommended",
    "similar",
    "related",
    "compare",
}

ACCESSORY_WORDS = {
    "case",
    "cover",
    "screen protector",
    "guard",
    "charger",
    "cable",
    "adapter",
    "earphones",
    "earbuds",
    "stand",
    "holder",
    "mount",
    "strap",
    "band",
    "sticker",
    "skin",
    "tempered glass",
    "tools",
}

KNOWN_BRANDS = {
    "apple",
    "samsung",
    "sony",
    "lg",
    "dell",
    "hp",
    "lenovo",
    "asus",
    "xiaomi",
    "realme",
    "vivo",
    "oppo",
    "oneplus",
    "google",
    "microsoft",
    "bose",
    "jbl",
    "boat",
    "marshall",
    "sennheiser",
    "noise",
    "nike",
    "adidas",
    "puma",
    "skybags",
    "wildcraft",
    "american tourister",
    "fastrack",
    "titan",
    "casio",
    "fossil",
    "arduino",
    "raspberry pi",
    "esp32",
    "intel",
    "amd",
    "nvidia",
    "texas instruments",
    "microchip",
}

CATEGORY_WORDS = {
    "laptop",
    "phone",
    "mobile",
    "tablet",
    "smartphone",
    "headphone",
    "earphone",
    "earbud",
    "earbuds",
    "speaker",
    "camera",
    "watch",
    "smartwatch",
    "bag",
    "backpack",
    "shirt",
    "shoe",
    "shoes",
    "sneaker",
    "book",
    "novel",
    "arduino",
    "raspberry",
    "sensor",
    "motor",
    "controller",
    "board",
}


class RelevanceScorer:
    def __init__(self, threshold: int = 40):
        self.threshold = threshold

    def score_product(self, product_name: str, search_term: str) -> dict:
        score = 0
        reasons: list[str] = []

        product_lower = (product_name or "").lower()
        search_lower = (search_term or "").lower()
        search_words = [w for w in search_lower.split() if len(w) >= 2]

        if search_lower and search_lower in product_lower:
            score += 50
            reasons.append("Exact phrase match (+50)")

        if search_words:
            matched = sum(1 for w in search_words if w in product_lower)
            if matched:
                score += matched * 10
                reasons.append(
                    f"{matched}/{len(search_words)} keywords matched (+{matched * 10})"
                )

        for brand in KNOWN_BRANDS:
            if brand in search_lower and brand in product_lower:
                score += 30
                reasons.append(f"Brand match: {brand} (+30)")
                break

        for cat in CATEGORY_WORDS:
            if cat in search_lower and cat in product_lower:
                score += 20
                reasons.append(f"Category match: {cat} (+20)")
                break

        if search_lower and product_lower:
            window = len(search_lower) + 6
            best_sim = 0.0
            if len(product_lower) <= window:
                best_sim = SequenceMatcher(None, search_lower, product_lower).ratio()
            else:
                for i in range(0, len(product_lower) - window + 1, 3):
                    chunk = product_lower[i : i + window]
                    sim = SequenceMatcher(None, search_lower, chunk).ratio()
                    best_sim = max(best_sim, sim)
            if 0.6 < best_sim < 0.9:
                fuzzy_score = int((best_sim - 0.6) * 50)
                if fuzzy_score > 0:
                    score += fuzzy_score
                    reasons.append(f"Fuzzy match: {best_sim:.0%} (+{fuzzy_score})")

        name_len = len(product_name or "")
        if 10 <= name_len <= 100:
            score += 15
            reasons.append("Good name length (+15)")
        elif name_len < 5:
            score -= 20
            reasons.append("Name too short (-20)")

        searching_for_accessory = any(acc in search_lower for acc in ACCESSORY_WORDS)
        if not searching_for_accessory:
            for accessory in ACCESSORY_WORDS:
                if accessory in product_lower:
                    score -= 40
                    reasons.append(f"Accessory penalty: {accessory} (-40)")
                    break

        score = max(0, min(100, score))
        return {"score": score, "reasons": reasons, "accept": score >= self.threshold}

    def filter_and_rank(self, products: list[dict], search_term: str) -> list[dict]:
        scored: list[dict] = []
        for product in products:
            name = product.get("name", "")
            if not name:
                continue
            result = self.score_product(name, search_term)
            if result["accept"]:
                product["_relevance_score"] = result["score"]
                product["_relevance_reasons"] = result["reasons"]
                scored.append(product)
            else:
                logger.debug(
                    f"Relevance rejected (score={result['score']}): {name}  reasons={result['reasons']}"
                )

        scored.sort(key=lambda p: p.get("_relevance_score", 0), reverse=True)
        filtered_count = len(products) - len(scored)
        if filtered_count > 0:
            logger.info(
                f"Relevance filter: kept {len(scored)}/{len(products)} products (threshold={self.threshold})"
            )
        return scored


class DataValidator:
    def __init__(self, min_price: float = 5.0, relevance_threshold: int = 20):
        self.rules = VALIDATION_RULES
        self.min_price = min_price
        self.scorer = RelevanceScorer(threshold=relevance_threshold)

    def validate_product(self, product: dict) -> bool:
        return self._validate_basic_quality(product)

    def _validate_basic_quality(self, product: dict) -> bool:
        if not product:
            return False
        name = product.get("name", "").strip()
        name_lower = name.lower()
        if not name:
            return False
        if not self.is_readable(name):
            logger.debug(f"Rejected unreadable name: {name!r}")
            return False
        if name_lower in GARBAGE_WORDS:
            logger.debug(f"Rejected garbage menu item: {name}")
            return False
        garbage_phrases = [
            "search for",
            "sort by",
            "filter by",
            "view all",
            "see more",
            "add to cart",
            "buying guide",
            "check each product page",
            "buying options",
        ]
        if any(phrase in name_lower for phrase in garbage_phrases):
            logger.debug(f"Rejected garbage phrase: {name}")
            return False
        if len(name) < 12:
            logger.debug(f"Rejected too-short name: {name}")
            return False
        price_float = product.get("price_float")
        if price_float is not None and price_float < self.min_price:
            logger.debug(
                f"Rejected low-price item (likely accessory): {name} - ₹{price_float}"
            )
            return False
        for field in ["name", "price"]:
            if field not in product:
                return False
            value = product[field]
            if value == "N/A":
                continue
            if not self._validate_field(field, value):
                return False
        return True

    @staticmethod
    def is_readable(text: str) -> bool:
        if not text:
            return False
        normal = len(re.findall(r"[A-Za-z0-9 ,.'&()+/\-]", text))
        return (normal / len(text)) >= 0.8

    def _validate_field(self, field: str, value: str) -> bool:
        if not value:
            return False
        rules = self.rules.get(field, {})
        if len(value) < rules.get("min_length", 1) or len(value) > rules.get(
            "max_length", 1000
        ):
            return False
        for pattern in rules.get("forbidden_patterns", []):
            if re.search(pattern, value, re.IGNORECASE):
                return False
        return True

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        text = " ".join(text.split())
        return re.sub(r"[\x00-\x1F\x7F-\x9F]", "", text).strip()

    def clean_price(self, price: str) -> float | None:
        if not price or price == "N/A":
            return None
        cleaned = re.sub(r"[^\d.]", "", price)
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    def filter_products(
        self, products: list[dict], search_term: str = ""
    ) -> list[dict]:
        if not products:
            return []

        # 🛡️ PHASE 4: PYDANTIC SANITY CHECK
        validated_products = []
        for p in products:
            # 1. Clean up the raw price string into a float
            p["price_float"] = self.clean_price(p.get("price", ""))

            # 2. Run it through Pydantic
            try:
                # We ignore extra fields (like 'source') so it doesn't crash
                validated = ProductSchema(**p)
                # Update the product dict with the cleaned data
                p["name"] = validated.name
                p["price_float"] = validated.price_float
                validated_products.append(p)
            except Exception as e:
                logger.debug(f"❌ Rejected by Schema: {p.get('name')} | Reason: {e}")
                continue

        if not validated_products:
            return []

        # Step 1 — normalize text
        for product in validated_products:
            raw_name = product.get("name", "")
            if "&amp;" in raw_name:
                product["name"] = raw_name.replace("&amp;", "&")
            product["name"] = self.clean_text(product.get("name", ""))
            product["price"] = self.clean_text(product.get("price", ""))

        # Step 2 — basic quality (menu items, garbage, etc.)
        quality_filtered = [
            p for p in validated_products if self._validate_basic_quality(p)
        ]

        # Step 3 — relevance scoring
        if search_term:
            ranked = self.scorer.filter_and_rank(quality_filtered, search_term)
        else:
            ranked = quality_filtered

        return ranked
