# ============================================================
# validators.py - Data validation, garbage filtering & relevance scoring
# ============================================================
# Ye file check karti hai ki scraper jo data laaya hai wo
# sach me product hai ya bas menu/filter ka junk text hai,
# aur fir relevance ke hisab se score karke best products rakhti hai.
# ============================================================

import re  # Regular expression ke liye import - pattern matching me kaam aata hai
import logging  # Debug logs print karne ke liye
from difflib import SequenceMatcher  # Fuzzy / typo-tolerant matching ke liye
from typing import Dict, List, Optional  # Type hints - code ko readable banata hai
from config import VALIDATION_RULES  # config.py se rules import kar rahe

logger = logging.getLogger(__name__)  # Apna logger banao - debugging me help karega

# --------------------------------------------------------
# GARBAGE_WORDS - ye sab words hai jo product NAHI hai
# Mostly menu items, filters, buttons, navigation text
# Jab bhi scraper in words ko product samajh ke pakad le,
# to hum usse reject kar denge
# --------------------------------------------------------
GARBAGE_WORDS = {
    # Navigation aur menu ke words - header/footer me milte hai
    "home", "men", "women", "categories", "clothing", "footwear",
    "accessories", "mobiles", "electronics", "toys and games",
    "bags, wallets & belts", "electronic kits", "science project kit",
    "search for products", "search for products, brands and more",
    "all categories", "all that's new", "new arrivals", "best sellers", "home decor",
    "home",

    # Filter options - sidebar me dikhte hai, products nahi hai
    "6 gb", "8 gb", "4 gb", "3 gb", "50% or more", "40% or more",
    "30% or more", "20% or more", "10% or more", "1 gb", "2 gb",

    # Action buttons aur UI text - click karne wale elements
    "special price", "buying guide", "myntra", "shopsy", "cleartrip",
    "buy more, save more", "check each product page", "add to cart",
    "view all", "see more", "show more", "load more", "filter by",
    "sort by", "price low to high", "price high to low",

    # Generic categories - site ke category labels, products nahi
    "plus size", "grooming", "winterwear", "night & loungewear",
    "ajio global", "poco", "flipkart", "amazon", "meesho",

    # Chhote generic words - aksar headers me dikhte hai
    "all", "new", "sale", "offers", "deals", "trending", "popular",
    "featured", "recommended", "similar", "related", "compare",
}

# Accessory words: if the user is NOT searching for these, any product
# whose name contains one of them is penalized (e.g. "iphone 13 case").
ACCESSORY_WORDS = {
    "case", "cover", "screen protector", "guard", "charger", "cable",
    "adapter", "earphones", "earbuds", "stand", "holder", "mount",
    "strap", "band", "sticker", "skin", "tempered glass", "tools",
}

# ============================================================
# Advanced relevance scoring — brand & category dictionaries
# ============================================================
# Match in BOTH search term AND product name to boost score.
# Extend these as you add more sites.
# ============================================================

KNOWN_BRANDS = {
    # Mobiles & laptops
    "apple", "samsung", "sony", "lg", "dell", "hp", "lenovo", "asus",
    "xiaomi", "realme", "vivo", "oppo", "oneplus", "google", "microsoft",
    # Audio / wearables
    "bose", "jbl", "boat", "marshall", "sennheiser", "noise",
    # Fashion
    "nike", "adidas", "puma", "skybags", "wildcraft", "american tourister",
    "fastrack", "titan", "casio", "fossil",
    # Electronics / DIY
    "arduino", "raspberry pi", "esp32", "intel", "amd", "nvidia",
    "texas instruments", "microchip",
}

CATEGORY_WORDS = {
    "laptop", "phone", "mobile", "tablet", "smartphone",
    "headphone", "earphone", "earbud", "earbuds", "speaker",
    "camera", "watch", "smartwatch",
    "bag", "backpack", "shirt", "shoe", "shoes", "sneaker",
    "book", "novel",
    "arduino", "raspberry", "sensor", "motor", "controller", "board",
}


# ============================================================
# RelevanceScorer
# ============================================================
class RelevanceScorer:
    """
    Multi-factor search-relevance scoring inspired by how search
    engines rank results. Each product gets a 0-100 score based on
    exact-phrase match, keyword overlap, brand match, category match,
    fuzzy (typo-tolerant) similarity, name length, and accessory
    penalty. Products scoring above `threshold` are kept.

    Attributes:
        threshold (int): minimum score to accept (default 40).
    """

    def __init__(self, threshold: int = 40):
        self.threshold = threshold

    def score_product(self, product_name: str, search_term: str) -> Dict:
        """
        Calculate relevance score for a single product.

        Returns:
            {
                'score':   int 0-100,
                'reasons': list[str] explaining the score,
                'accept':  bool (score >= threshold)
            }
        """
        score = 0
        reasons: List[str] = []

        product_lower = (product_name or "").lower()
        search_lower = (search_term or "").lower()
        search_words = [w for w in search_lower.split() if len(w) >= 2]

        # 1. EXACT PHRASE MATCH (+50)
        if search_lower and search_lower in product_lower:
            score += 50
            reasons.append("Exact phrase match (+50)")

        # 2. KEYWORD MATCHES (+10 per word)
        if search_words:
            matched = sum(1 for w in search_words if w in product_lower)
            if matched:
                score += matched * 10
                reasons.append(
                    f"{matched}/{len(search_words)} keywords matched (+{matched * 10})"
                )

        # 3. BRAND MATCH (+30)
        for brand in KNOWN_BRANDS:
            if brand in search_lower and brand in product_lower:
                score += 30
                reasons.append(f"Brand match: {brand} (+30)")
                break

        # 4. CATEGORY MATCH (+20)
        for cat in CATEGORY_WORDS:
            if cat in search_lower and cat in product_lower:
                score += 20
                reasons.append(f"Category match: {cat} (+20)")
                break

        # 5. FUZZY MATCH — typo tolerance using SequenceMatcher.
        #    Sliding-window comparison so long product names don't
        #    dilute the score. Only counts in the 60-90% band; perfect
        #    matches are already rewarded by the exact-phrase rule.
        if search_lower and product_lower:
            window = len(search_lower) + 6
            best_sim = 0.0
            if len(product_lower) <= window:
                best_sim = SequenceMatcher(None, search_lower, product_lower).ratio()
            else:
                for i in range(0, len(product_lower) - window + 1, 3):
                    chunk = product_lower[i:i + window]
                    sim = SequenceMatcher(None, search_lower, chunk).ratio()
                    if sim > best_sim:
                        best_sim = sim
            if 0.6 < best_sim < 0.9:
                fuzzy_score = int((best_sim - 0.6) * 50)  # 0-15
                if fuzzy_score > 0:
                    score += fuzzy_score
                    reasons.append(f"Fuzzy match: {best_sim:.0%} (+{fuzzy_score})")

        # 6. LENGTH APPROPRIATENESS (+15 / -20)
        name_len = len(product_name or "")
        if 10 <= name_len <= 100:
            score += 15
            reasons.append("Good name length (+15)")
        elif name_len < 5:
            score -= 20
            reasons.append("Name too short (-20)")

        # 7. ACCESSORY PENALTY (-40) — only if user is NOT searching
        #    for accessories (e.g. "iphone 13 case" is allowed).
        searching_for_accessory = any(
            acc in search_lower for acc in ACCESSORY_WORDS
        )
        if not searching_for_accessory:
            for accessory in ACCESSORY_WORDS:
                if accessory in product_lower:
                    score -= 40
                    reasons.append(f"Accessory penalty: {accessory} (-40)")
                    break

        # Clamp to 0-100
        score = max(0, min(100, score))

        return {
            "score": score,
            "reasons": reasons,
            "accept": score >= self.threshold,
        }

    def filter_and_rank(self, products: List[Dict], search_term: str) -> List[Dict]:
        """
        Score, filter, and rank a list of products.

        Each accepted product gains two fields:
            _relevance_score   (int)
            _relevance_reasons (list[str])
        Returns the survivors sorted best-first.
        """
        scored: List[Dict] = []
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
                    f"Relevance rejected (score={result['score']}): "
                    f"{name}  reasons={result['reasons']}"
                )

        scored.sort(key=lambda p: p.get("_relevance_score", 0), reverse=True)

        filtered_count = len(products) - len(scored)
        if filtered_count > 0:
            logger.info(
                f"Relevance filter: kept {len(scored)}/{len(products)} "
                f"products (threshold={self.threshold})"
            )
        return scored


# ============================================================
# DataValidator
# ============================================================
class DataValidator:
    """
    DataValidator class - har product ko check karti hai ki wo valid
    hai ya nahi, fir RelevanceScorer ke saath rank karti hai.

    Pipeline:
        1. Basic quality checks (garbage, length, mojibake, price)
        2. HTML-entity cleanup
        3. Multi-factor relevance scoring
        4. Rank by relevance (best first)
    """

    def __init__(self, min_price: float = 500.0, relevance_threshold: int = 40):
        self.rules = VALIDATION_RULES
        self.min_price = min_price
        self.scorer = RelevanceScorer(threshold=relevance_threshold)

    # ----------------------------------------------------------------
    # Backward-compat: legacy callers still call validate_product().
    # We delegate to the new quality check.
    # ----------------------------------------------------------------
    def validate_product(self, product: Dict) -> bool:
        return self._validate_basic_quality(product)

    def _validate_basic_quality(self, product: Dict) -> bool:
        """
        Cheap structural checks (NOT relevance):
        empty name, garbage menu text, mojibake, suspiciously low price.
        """
        if not product:
            return False

        name = product.get("name", "").strip()
        name_lower = name.lower()

        if not name:
            return False

        # Mojibake / binary guard
        if not self.is_readable(name):
            logger.debug(f"Rejected unreadable name: {name!r}")
            return False

        # Garbage menu words
        if name_lower in GARBAGE_WORDS:
            logger.debug(f"Rejected garbage menu item: {name}")
            return False

        # Garbage UI phrases
        garbage_phrases = [
            "search for", "sort by", "filter by", "view all",
            "see more", "add to cart", "buying guide",
            "check each product page", "buying options",
        ]
        if any(phrase in name_lower for phrase in garbage_phrases):
            logger.debug(f"Rejected garbage phrase: {name}")
            return False

        # Too short = likely a menu/button
        if len(name) < 12:
            logger.debug(f"Rejected too-short name: {name}")
            return False

        # Suspiciously cheap = likely an accessory
        price_float = product.get("price_float")
        if price_float is not None and price_float < self.min_price:
            logger.debug(
                f"Rejected low-price item (likely accessory): {name} - ₹{price_float}"
            )
            return False

        # Field-level rules from config.py
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
        """Reject names that look like mojibake (wrong-charset decode)."""
        if not text:
            return False
        normal = len(re.findall(r"[A-Za-z0-9 ,.'&()+/\-]", text))
        return (normal / len(text)) >= 0.8

    def _validate_field(self, field: str, value: str) -> bool:
        if not value:
            return False
        rules = self.rules.get(field, {})
        if len(value) < rules.get("min_length", 1) or len(value) > rules.get("max_length", 1000):
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

    def clean_price(self, price: str) -> Optional[float]:
        if not price or price == "N/A":
            return None
        cleaned = re.sub(r"[^\d.]", "", price)
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    def filter_products(self, products: List[Dict], search_term: str = "") -> List[Dict]:
        """
        Full pipeline:
            1. Normalize every product (price_float, entity cleanup, trim).
            2. Drop anything that fails _validate_basic_quality.
            3. Score survivors with RelevanceScorer and keep those
               above `relevance_threshold`.
            4. Return them sorted best-first.
        """
        if not products:
            return []

        # Step 1 — normalize
        for product in products:
            product["price_float"] = self.clean_price(product.get("price", ""))
            raw_name = product.get("name", "")
            if "&amp;" in raw_name:
                product["name"] = raw_name.replace("&amp;", "&")
            product["name"] = self.clean_text(product.get("name", ""))
            product["price"] = self.clean_text(product.get("price", ""))

        # Step 2 — basic quality
        quality_filtered = [
            p for p in products if self._validate_basic_quality(p)
        ]
        if not quality_filtered:
            logger.info(
                f"Validator: 0/{len(products)} products passed basic quality."
            )
            return []

        # Step 3 — relevance scoring (only if we have a search term)
        if search_term:
            ranked = self.scorer.filter_and_rank(quality_filtered, search_term)
        else:
            ranked = quality_filtered

        # Summary log
        logger.info(
            f"Validator: {len(ranked)} relevant products kept from {len(products)} raw "
            f"(quality: {len(quality_filtered)}, threshold={self.scorer.threshold})."
        )
        return ranked
