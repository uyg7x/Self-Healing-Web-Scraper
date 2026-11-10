import json
import logging
import re

from core.config import GEMINI_API_KEY, GEMINI_MODEL, LLM_HTML_MAX_CHARS

logger = logging.getLogger(__name__)


class LLMHealer:
    _PROMPT_TEMPLATE = """You are a web-scraping assistant. Read the HTML below and
extract any products that match the search term: "{search_term}".

Return ONLY a JSON list (no explanation, no markdown fences, no extra text).
Each item must have exactly these keys:
  - "name":  the product's display name (string)
  - "price": the price as shown on the page, e.g. "₹1,299" or "$19.99" (string)
  - "link":  the product's relative or absolute URL (string). If no link
            is visible, use "N/A".

If you cannot find any matching products, return an empty list: []

HTML (may be truncated):
{html}
"""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.runtime_enabled = True
        self.api_key = api_key if api_key is not None else GEMINI_API_KEY
        self.model_name = model if model is not None else GEMINI_MODEL
        self.model = None

        if self.api_key:
            self._configure()

    def heal(self, html: str, search_term: str) -> list[dict]:
        
        if not self.runtime_enabled:
            logger.info("LLMHealer: skipped (disabled by user at startup)")
            return []

        
        if not self.api_key:
            logger.info("LLMHealer: skipped (no GEMINI_API_KEY)")
            return []

        if not html or not html.strip():
            return []

        if self.model is None:
            self._configure()
            if self.model is None:
                return []

        try:
            trimmed = self._trim_html(html)
            prompt = self._PROMPT_TEMPLATE.format(
                search_term=search_term or "", html=trimmed
            )
            response = self.model.generate_content(prompt)
            raw_text = self._extract_text(response)
            products = self._parse_products(raw_text)
            logger.info(f"LLMHealer: Gemini returned {len(products)} product(s)")
            return products
        except Exception as e:
            logger.error(f"LLMHealer: error, returning []: {e}")
            return []


    
    def _configure(self) -> None:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            logger.info(f"LLMHealer: configured model '{self.model_name}'")
        except ImportError:
            logger.error("LLMHealer: google-generativeai not installed")
            self.model = None
        except Exception as e:
            logger.error(f"LLMHealer: configure failed: {e}")
            self.model = None

    def _trim_html(self, html: str) -> str:
        cleaned = re.sub(
            r"<script\b[^>]*>.*?</script>", "", html, flags=re.I | re.S
        )
        cleaned = re.sub(
            r"<style\b[^>]*>.*?</style>", "", cleaned, flags=re.I | re.S
        )
        cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.S)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) > LLM_HTML_MAX_CHARS:
            cleaned = cleaned[:LLM_HTML_MAX_CHARS] + "\n... [truncated]"
        return cleaned

    def _extract_text(self, response) -> str:
        try:
            if hasattr(response, "text") and response.text:
                return response.text
        except Exception:
            pass
        try:
            candidates = getattr(response, "candidates", None) or []
            if candidates:
                parts = candidates[0].content.parts
                if parts and hasattr(parts[0], "text"):
                    return parts[0].text
        except Exception:
            pass
        return str(response)

    def _parse_products(self, raw: str) -> list[dict]:
        if not raw:
            return []
        text = raw.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)

        match = re.search(r"\[.*\]", text, flags=re.S)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []

        cleaned = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name:
                continue
            cleaned.append(
                {
                    "name": name,
                    "price": str(item.get("price", "N/A")).strip() or "N/A",
                    "link": str(item.get("link", "N/A")).strip() or "N/A",
                    "specs": "N/A",
                    "method": "llm",
                }
            )
        return cleaned
