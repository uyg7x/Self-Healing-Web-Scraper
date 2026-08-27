"""
QWEN AI FALLBACK (Strategy 6 - Ultimate Fallback)
=================================================

Uses TCET CoE AI Gateway (Qwen3.6-35B) to extract product data when ALL
other strategies fail (JSON-LD, CSS, regex, fuzzy self-heal, Gemini).

Extracts: name, price, image_url, link, specs.

This is how real AI search engines (Perplexity, ChatGPT-with-browsing)
work under the hood — an LLM reads the messy HTML and returns structured
data. We're applying that same idea as the LAST line of defense.

Key design points:
- The OpenAI SDK is imported lazily so the rest of the project keeps
  running even if the user hasn't installed `openai`.
- The class NEVER raises. On any error it returns `[]` so the caller
  can simply fall through to the next strategy.
- API key is read from env (COE_AI_KEY) or config fallback.
"""

import json
import logging
import re
from typing import List, Dict, Optional

from config import COE_AI_CONFIG

logger = logging.getLogger(__name__)


class QwenFallback:
    """
    Uses the campus-hosted Qwen3.6 model to extract product data from raw HTML.

    Usage:
        qwen = QwenFallback()
        products = qwen.extract_products(html, search_term="Asus VivoBook")
        # -> [{"name": "...", "price": "...", "image_url": "...", "link": "..."}, ...]
        # -> [] on any failure
    """

    # The exact prompt sent to Qwen. Forces a JSON-only reply so parsing
    # is safe even if the model adds stray text.
    _PROMPT_TEMPLATE = """You are an expert web-scraping assistant. Extract ALL products from the HTML below.

Search Term: "{search_term}"
Target Site: {target_site}

INSTRUCTIONS:
1. Find every product that matches the search term.
2. For EACH product, return EXACTLY these fields:
   - "name":       Product title/name (string)
   - "price":      Price as shown (e.g. "₹79,900" or "Rs. 1,299") (string)
   - "image_url":  Full URL of the product image from <img> tags / src (string)
   - "link":       Product page URL — absolute if possible (string, or "N/A")
   - "specs":      Key specifications if visible (string, or "N/A")

3. Return ONLY a valid JSON array. NO explanations, NO markdown fences,
   NO extra text before or after the array.

Example response:
[
  {{
    "name": "Apple iPhone 15 (128 GB) - Blue",
    "price": "₹79,900",
    "image_url": "https://m.media-amazon.com/images/I/71xb2xkN5qL._SX679.jpg",
    "link": "https://www.amazon.in/dp/B0CHX1W1XY",
    "specs": "128 GB, Blue, 5G"
  }}
]

If no products match, return: []

Now extract from this HTML:
"""

    def __init__(self):
        self.enabled = bool(COE_AI_CONFIG.get("enabled", False))
        self.base_url = COE_AI_CONFIG.get("base_url", "")
        self.api_key = COE_AI_CONFIG.get("api_key", "")
        self.model = COE_AI_CONFIG.get("model", "qwen3.6")
        self.max_tokens = int(COE_AI_CONFIG.get("max_tokens", 2048))
        self.html_max_chars = int(COE_AI_CONFIG.get("html_max_chars", 30000))

        self.client = None
        if self.enabled and self.api_key:
            try:
                # Imported here (lazy) so missing 'openai' package doesn't
                # crash the rest of the scraper.
                from openai import OpenAI
                self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
                logger.info("✅ Qwen Fallback: Connected to CoE AI Gateway (%s)", self.base_url)
            except Exception as e:
                logger.error("❌ Qwen Fallback: failed to initialise OpenAI client: %s", e)
                self.enabled = False
        else:
            if self.enabled:
                logger.warning("Qwen Fallback enabled in config but no api_key set — disabling.")
            self.enabled = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract_products(
        self,
        html: str,
        search_term: str,
        target_site: str = "",
    ) -> List[Dict]:
        """
        Ask Qwen to extract products from raw HTML.

        Returns a list of dicts with keys:
            name, price, image_url, link, specs, method
        Returns [] on any failure (never raises).
        """
        if not self.enabled or not self.client:
            logger.debug("Qwen Fallback not enabled, skipping...")
            return []

        if not html or len(html) < 100:
            logger.warning("HTML too short for Qwen extraction (%d chars)", len(html or ""))
            return []

        cleaned_html = self._trim_html(html)
        prompt = self._build_prompt(search_term, target_site)
        full_prompt = f"{prompt}\n\nHTML Content:\n{cleaned_html}"

        try:
            logger.info(
                "🔍 Qwen Fallback: extracting products for '%s' (target=%s)...",
                search_term, target_site or "any",
            )
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": full_prompt}],
                max_tokens=self.max_tokens,
                temperature=0.1,  # low = consistent extraction
            )
            raw_text = (response.choices[0].message.content or "").strip()
            products = self._parse_response(raw_text)
            logger.info("✅ Qwen Fallback: extracted %d product(s)", len(products))
            return products
        except Exception as e:
            logger.error("❌ Qwen Fallback failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _trim_html(self, html: str) -> str:
        """Strip <script>, <style>, comments, collapse whitespace, cap length."""
        cleaned = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"<style\b[^>]*>.*?</style>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) > self.html_max_chars:
            cleaned = cleaned[: self.html_max_chars] + "\n... [truncated]"
        return cleaned

    def _build_prompt(self, search_term: str, target_site: str) -> str:
        site_line = f"Target Site: {target_site}\n" if target_site else ""
        return self._PROMPT_TEMPLATE.format(
            search_term=search_term, target_site=site_line.rstrip()
        )

    def _parse_response(self, raw_text: str) -> List[Dict]:
        """Parse Qwen's reply into a list of clean product dicts."""
        if not raw_text:
            return []

        # Strip ```json ... ``` fences if the model wrapped the answer.
        raw_text = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.IGNORECASE)
        raw_text = re.sub(r"\s*```$", "", raw_text.strip())

        try:
            products = json.loads(raw_text)
        except json.JSONDecodeError:
            # Last-ditch: grab the first [...] block.
            match = re.search(r"\[.*\]", raw_text, flags=re.DOTALL)
            if not match:
                logger.error("Qwen response contained no JSON array.")
                return []
            try:
                products = json.loads(match.group(0))
            except json.JSONDecodeError:
                logger.error("Qwen response was not valid JSON.")
                return []

        if not isinstance(products, list):
            logger.error("Qwen response was not a list (got %s).", type(products).__name__)
            return []

        cleaned: List[Dict] = []
        for item in products:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name or len(name) < 5:
                continue
            cleaned.append({
                "name":      name,
                "price":     str(item.get("price", "N/A")).strip(),
                "image_url": str(item.get("image_url", "")).strip(),
                "link":      str(item.get("link", "N/A")).strip(),
                "specs":     str(item.get("specs", "N/A")).strip(),
                "method":    "qwen_ai_fallback",
            })
        return cleaned
