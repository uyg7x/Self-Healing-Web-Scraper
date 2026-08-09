# ============================================================
# validators.py - Data validation aur garbage filtering ka logic
# ============================================================
# Ye file check karti hai ki scraper jo data laaya hai wo
# sach me product hai ya bas menu/filter ka junk text hai
# ============================================================

import re  # Regular expression ke liye import - pattern matching me kaam aata hai
import logging  # Debug logs print karne ke liye
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


class DataValidator:
    """
    DataValidator class - har product ko check karti hai ki wo valid hai ya nahi.

    Iska kaam hai:
    1. Garbage/menu text ko reject karna
    2. Bahut chhote names ko reject karna
    3. Bahut kam price wale items ko reject karna (accessories hote hai)
    4. HTML entities ko clean karna (&amp; ko & me convert karna)
    """

    def __init__(self):
        # Constructor - rules ko load karo config.py se
        self.rules = VALIDATION_RULES

    def validate_product(self, product: Dict) -> bool:
        """
        Ek single product ko validate karo.
        Returns True agar product valid hai, False agar garbage hai.
        """
        # Agar product None ya empty dict hai to direct reject
        if not product:
            return False

        # Product ka naam nikalo aur lowercase me convert karo for comparison
        name = product.get("name", "").strip()
        name_lower = name.lower()

        # ---- CHECK 1: Agar naam GARBAGE_WORDS list me hai to reject ----
        # Kyunki "home", "cart", "login" jaise words kabhi product nahi hote
        if name_lower in GARBAGE_WORDS:
            logger.debug(f"Rejected garbage menu item: {name}")
            return False

        # ---- CHECK 2: Partial match check - kuch phrases agar naam me hai to reject ----
        # Jaise "sort by" ya "filter by" - ye UI elements hai, products nahi
        garbage_phrases = ["search for", "sort by", "filter by", "view all",
                          "see more", "add to cart", "buying guide"]
        if any(phrase in name_lower for phrase in garbage_phrases):
            logger.debug(f"Rejected garbage phrase: {name}")
            return False

        # ---- CHECK 3: Amazon block text ko reject karo ----
        # Amazon kabhi kabhi "Check each product page" jaisa text product ki jagah dikhata hai
        if "check each product page" in name_lower or "buying options" in name_lower:
            return False

        # ---- CHECK 4: Bahut chhota naam = likely menu item ----
        # 12 chars se kam = usually category/button text hota hai
        if len(name) < 12:
            logger.debug(f"Rejected too-short name: {name}")
            return False

        # ---- CHECK 5: Suspiciously low price wale items reject karo ----
        # Kyunki Arduino jaisa search kar rahe hai to starter kit (₹800+)
        # chahiye, alag sensors (₹50-₹300) nahi chahiye
        # Note: price_float pehle calculate hona chahiye - filter_products me hota hai
        price_float = product.get("price_float")
        if price_float is not None and price_float < 500:
            logger.debug(f"Rejected low-price item (likely accessory): {name} - ₹{price_float}")
            return False

        # ---- CHECK 6: Har field ko uske rule ke against validate karo ----
        for field in ["name", "price"]:
            if field not in product:
                return False
            value = product[field]
            # "N/A" ko skip karo - matlab data missing hai but invalid nahi
            if value == "N/A":
                continue
            if not self._validate_field(field, value):
                return False

        # Sab checks pass ho gaye - product valid hai!
        return True

    def _validate_field(self, field: str, value: str) -> bool:
        """
        Ek specific field ko uske rule ke against check karo.
        Private method hai - underscore se start hota hai.
        """
        # Agar value empty hai to invalid
        if not value:
            return False
        # Us field ke rules nikalo config se
        rules = self.rules.get(field, {})
        # Length check - min aur max ke beech hona chahiye
        if len(value) < rules.get("min_length", 1) or len(value) > rules.get("max_length", 1000):
            return False
        # Forbidden patterns check - jaise URLs ya "click here" jaisa text
        for pattern in rules.get("forbidden_patterns", []):
            if re.search(pattern, value, re.IGNORECASE):
                return False
        # Sab pass - field valid hai
        return True

    def clean_text(self, text: str) -> str:
        """
        Text ko clean karo - extra spaces aur invisible characters hatao.
        Useful hai jab HTML se text nikala ho aur extra whitespace aa jaye.
        """
        if not text:
            return ""
        # Multiple spaces ko single space me convert karo
        text = " ".join(text.split())
        # Invisible Unicode characters (newlines, tabs, control chars) hatao
        return re.sub(r"[\x00-\x1F\x7F-\x9F]", "", text).strip()

    def clean_price(self, price: str) -> Optional[float]:
        """
        Price string se number nikalo.
        "₹1,299.99" se 1299.99 return karega.
        Returns None agar parse nahi ho paya.
        """
        # Empty ya N/A ke liye None return karo
        if not price or price == "N/A":
            return None
        # Sirf digits aur decimal point rakho, baaki sab hata do (₹, $, comma, etc.)
        cleaned = re.sub(r"[^\d.]", "", price)
        if not cleaned:
            return None
        try:
            # Float me convert karo
            return float(cleaned)
        except ValueError:
            # Agar convert nahi hua to None return karo
            return None

    def filter_products(self, products: List[Dict]) -> List[Dict]:
        """
        Pura product list filter karo - sirf valid products rakho.
        Ye main function hai jo har product ko individually check karta hai.
        """
        valid_products = []
        for product in products:
            # IMPORTANT FIX: Pehle price_float calculate karo
            # taaki validate_product ko price check me use kar sake
            product["price_float"] = self.clean_price(product.get("price", ""))

            # HTML entities clean karo - &amp; ko & me convert karo
            # Kyunki HTML me "&" ko "&amp;" likha hota hai encoding ke liye
            raw_name = product.get("name", "")
            if "&amp;" in raw_name:
                product["name"] = raw_name.replace("&amp;", "&")

            # Validate karo - agar valid hai to list me add karo
            if self.validate_product(product):
                # Final cleanup - text ko trim karo
                product["name"] = self.clean_text(product.get("name", ""))
                product["price"] = self.clean_text(product.get("price", ""))
                valid_products.append(product)
            else:
                # Reject hua to debug log me batao
                logger.debug(f"Filtered out: {product.get('name', 'unknown')}")

        # Summary log - kitne raw the, kitne valid bache
        logger.info(f"Filtered down to {len(valid_products)} clean products from {len(products)} raw.")
        return valid_products