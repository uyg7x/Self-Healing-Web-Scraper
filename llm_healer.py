"""
LLM HEALER
==========

5th (and LAST) fallback strategy for the scraper.

When JSON-LD, CSS selectors, regex, and fuzzy self-healing all fail to
extract products from a page, we ask Google's Gemini AI to "read" the
raw HTML and return the products it can spot.

Why this is a great last-resort:
- Gemini is great at understanding messy, real-world HTML
- Free tier (gemini-2.0-flash) is fast and good enough for this task
- It survives even totally redesigned sites because it understands
  text/semantics, not CSS structure

The class is intentionally beginner-friendly:
- One public method: `heal(html, search_term)`
- Returns a plain Python list of dicts
- NEVER raises — on any error it returns `[]`
"""

import json
import logging
import re
from typing import List, Dict, Optional

# We import the SDK lazily (inside the method) so that the rest of the
# scraper can still run on machines where google-generativeai isn't
# installed or where there's no API key. This keeps "import llm_healer"
# cheap and safe.
#
# `import google.generativeai as genai`  <- happens inside _configure()

from config import GEMINI_API_KEY, GEMINI_MODEL, LLM_HTML_MAX_CHARS

logger = logging.getLogger(__name__)


class LLMHealer:
    """
    Uses Google Gemini as a last-resort "smart reader" of messy HTML.

    Usage:
        healer = LLMHealer()
        products = healer.heal(html_text, search_term="Harry Potter Books")
        # products -> [{"name": "...", "price": "...", "link": "..."}, ...]
        # or [] if nothing was found / anything went wrong
    """

    # The exact prompt we send to Gemini. We force it to reply with
    # ONLY a JSON list so we can parse it safely.
    _PROMPT_TEMPLATE = """You are a web-scraping assistant. Read the HTML below and
extract any products that match the search term: "{search_term}".

Return ONLY a JSON list (no explanation, no markdown fences, no extra text).
Each item must have exactly these keys:
  - "name":  the product's display name (string)
  - "price": the price as shown on the page, e.g. "₹1,299" or "$19.99" (string)
  - "link":  the product's relative or absolute URL (string). If no link
            is visible, use "N/A".

If you cannot find any matching products, return an empty list: []

Example response:
[{{"name": "Harry Potter and the Sorcerer's Stone", "price": "₹399", "link": "/book/harry-potter-1"}}]

HTML (may be truncated):
{html}
"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Args:
            api_key: Gemini API key. If None, we read from config.GEMINI_API_KEY.
            model:   Gemini model name. If None, we read from config.GEMINI_MODEL.
        """
        self.api_key = api_key if api_key is not None else GEMINI_API_KEY
        self.model_name = model if model is not None else GEMINI_MODEL
        # `self.model` stays None until we successfully configure Gemini.
        self.model = None

        # If we have a key, try to configure the SDK right away so we
        # fail fast on a bad key instead of mid-scrape.
        if self.api_key:
            self._configure()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def heal(self, html: str, search_term: str) -> List[Dict]:
        """
        Ask Gemini to extract products from `html` for `search_term`.

        Returns a list of dicts: [{"name", "price", "link"}, ...]
        Returns [] on ANY error or when nothing is found.
        """
        # Guard 1: no key -> can't do anything
        if not self.api_key:
            logger.warning("LLMHealer: no GEMINI_API_KEY set, skipping LLM strategy.")
            return []

        # Guard 2: empty HTML
        if not html or not html.strip():
            logger.warning("LLMHealer: empty HTML passed in, skipping.")
            return []

        # Guard 3: SDK never configured (e.g. bad key at startup)
        if self.model is None:
            self._configure()
            if self.model is None:
                return []  # configure() already logged the error

        try:
            trimmed = self._trim_html(html)
            prompt = self._PROMPT_TEMPLATE.format(
                search_term=search_term or "",
                html=trimmed,
            )

            logger.info(
                f"LLMHealer: asking Gemini ({self.model_name}) "
                f"for '{search_term}' ({len(trimmed)} chars of HTML)..."
            )

            response = self.model.generate_content(prompt)
            raw_text = self._extract_text(response)

            products = self._parse_products(raw_text)
            logger.info(f"LLMHealer: Gemini returned {len(products)} product(s).")
            return products

        except Exception as e:
            # NEVER let the LLM step crash the scraper.
            logger.error(f"LLMHealer: unexpected error, returning []: {e}")
            return []

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _configure(self) -> None:
        """
        Configure the google-generativeai SDK. Sets self.model on success,
        leaves it as None on failure (and logs why).
        """
        try:
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"LLMHealer: configured Gemini model '{self.model_name}'.")
        except ImportError:
            logger.error(
                "LLMHealer: 'google-generativeai' is not installed. "
                "Run: pip install google-generativeai"
            )
            self.model = None
        except Exception as e:
            logger.error(f"LLMHealer: failed to configure Gemini SDK: {e}")
            self.model = None

    def _trim_html(self, html: str) -> str:
        """
        Make HTML smaller and friendlier for the LLM:
        - Drop <script> and <style> blocks entirely
        - Drop HTML comments
        - Cap the total length so we stay well under token limits

        We use simple regex because we want this to be fast and
        dependency-free (we don't need full HTML parsing here).
        """
        # 1. Remove <script>...</script> blocks (case-insensitive, dotall)
        cleaned = re.sub(
            r"<script\b[^>]*>.*?</script>",
            "",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        # 2. Remove <style>...</style> blocks
        cleaned = re.sub(
            r"<style\b[^>]*>.*?</style>",
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        # 3. Remove HTML comments <!-- ... -->
        cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.DOTALL)

        # 4. Collapse runs of whitespace so the prompt stays compact
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # 5. Hard cap on length (default 20,000 chars)
        if len(cleaned) > LLM_HTML_MAX_CHARS:
            cleaned = cleaned[:LLM_HTML_MAX_CHARS] + "\n... [truncated]"

        return cleaned

    def _extract_text(self, response) -> str:
        """
        Pull plain text out of a Gemini response object.

        Different SDK versions expose the text slightly differently, so we
        try a few common spots and fall back to str() if needed.
        """
        try:
            # Newer SDK: response.text
            if hasattr(response, "text") and response.text:
                return response.text
        except Exception:
            pass

        try:
            # Older SDK: response.candidates[0].content.parts[0].text
            candidates = getattr(response, "candidates", None) or []
            if candidates:
                parts = candidates[0].content.parts
                if parts and hasattr(parts[0], "text"):
                    return parts[0].text
        except Exception:
            pass

        # Last resort
        return str(response)

    def _parse_products(self, raw: str) -> List[Dict]:
        """
        Parse Gemini's reply into a clean list of product dicts.

        We are very defensive here because LLMs sometimes:
        - wrap output in ```json ... ``` fences
        - add a sentence before/after the JSON
        - return slightly malformed JSON

        Strategy:
        1. Strip markdown code fences if present
        2. Find the first "[" ... last "]" block
        3. json.loads() it
        4. Normalize each item to {name, price, link}
        Any failure -> return [].
        """
        if not raw:
            return []

        text = raw.strip()

        # 1. Strip ```json ... ``` or ``` ... ``` fences
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)

        # 2. Pull out the first JSON list [...] from the reply.
        #    This handles cases where Gemini adds a sentence around it.
        match = re.search(r"\[.*\]", text, flags=re.DOTALL)
        if not match:
            logger.debug("LLMHealer: no JSON list found in Gemini reply.")
            return []
        json_text = match.group(0)

        # 3. Actually parse it
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"LLMHealer: Gemini reply was not valid JSON: {e}")
            return []

        if not isinstance(data, list):
            logger.error("LLMHealer: Gemini reply was JSON but not a list.")
            return []

        # 4. Normalize each item so the rest of the pipeline can rely on
        #    the same shape it gets from other strategies.
        cleaned: List[Dict] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            price = str(item.get("price", "")).strip()
            link = str(item.get("link", "N/A")).strip() or "N/A"

            # Skip rows that have nothing useful
            if not name:
                continue

            cleaned.append(
                {
                    "name": name,
                    "price": price or "N/A",
                    "link": link,
                    "specs": "N/A",
                    "method": "llm",  # helps with debugging / CSV reports
                }
            )

        return cleaned
