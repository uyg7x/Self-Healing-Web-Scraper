import json
import logging
import re

from core.config import COE_AI_CONFIG

logger = logging.getLogger(__name__)


class QwenFallback:
    _PROMPT_TEMPLATE = """You are an expert e-commerce data extraction engine.
Analyze the HTML below and extract product information for search term: "{search_term}"

Target Site: {target_site}
Base Domain: {base_domain}

RULES:
1. EXACT SELLING PRICE - ignore MRP, strike-through, EMI prices.
2. IMAGE URL - absolute https URL from <img> or JSON-LD.
3. PRODUCT LINK - absolute URL from <a href> or JSON-LD.
4. SPECIFICATIONS - key specs from <meta> or <li>.

Return ONLY a valid JSON array, no markdown, no prose:
[
  {{
    "name": "Exact product title",
    "price": "₹XX,XXX",
    "image_url": "https://...",
    "link": "https://...",
    "specs": "key specs"
  }}
]

If nothing matches, return exactly: []

HTML:
"""

    def __init__(self):
        self.runtime_enabled = True
        self.config_enabled = bool(COE_AI_CONFIG.get("enabled", False))
        self.base_url = COE_AI_CONFIG.get("base_url", "")
        self.api_key = COE_AI_CONFIG.get("api_key", "")
        self.model = COE_AI_CONFIG.get("model", "qwen3.6")
        self.max_tokens = int(COE_AI_CONFIG.get("max_tokens", 2048))
        self.html_max_chars = int(COE_AI_CONFIG.get("html_max_chars", 30000))

        self.client = None
        if self.config_enabled and self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)
                logger.info(f"QwenFallback: connected to {self.base_url}")
            except Exception as e:
                logger.error(f"QwenFallback: client init failed: {e}")
                self.client = None

    @property
    def enabled(self) -> bool:
        return self.runtime_enabled and self.client is not None

    def extract_products(
        self, html: str, search_term: str, target_site: str = "", base_domain: str = ""
    ) -> list[dict]:
        if not self.runtime_enabled:
            logger.info("QwenFallback: skipped (disabled by user at startup)")
            return []
        if not self.config_enabled:
            logger.info("QwenFallback: skipped (config disabled)")
            return []
        if not self.client:
            logger.info("QwenFallback: skipped (no client / no key)")
            return []
        if not html or len(html) < 100:
            return []

        cleaned = self._trim_html(html)
        domain = base_domain or self._guess_domain(html, target_site)
        prompt = self._PROMPT_TEMPLATE.format(
            search_term=search_term,
            target_site=target_site,
            base_domain=domain,
        ) + cleaned

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.max_tokens,
                temperature=0.1,
            )
            raw = (resp.choices[0].message.content or "").strip()
            return self._parse(raw)
        except Exception as e:
            logger.error(f"QwenFallback: request failed: {e}")
            return []

    def _trim_html(self, html: str) -> str:
        cleaned = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.I | re.S)
        cleaned = re.sub(r"<style\b[^>]*>.*?</style>", "", cleaned, flags=re.I | re.S)
        cleaned = re.sub(r"<!--.*?-->", "", cleaned, flags=re.S)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if len(cleaned) > self.html_max_chars:
            cleaned = cleaned[: self.html_max_chars] + "\n... [truncated]"
        return cleaned

    def _guess_domain(self, html: str, target_site: str) -> str:
        match = re.search(r"https?://[^/]+", html)
        if match:
            return match.group(0)
        return target_site or ""

    def _parse(self, raw: str) -> list[dict]:
        if not raw:
            return []
        text = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.I)
        text = re.sub(r"\s*```$", "", text)

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\[.*\]", text, flags=re.S)
            if not m:
                return []
            try:
                data = json.loads(m.group(0))
            except json.JSONDecodeError:
                return []
        if not isinstance(data, list):
            return []

        cleaned = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            if not name or len(name) < 5:
                continue
            cleaned.append(
                {
                    "name": name,
                    "price": str(item.get("price", "N/A")).strip() or "N/A",
                    "image_url": str(item.get("image_url", "")).strip(),
                    "link": str(item.get("link", "N/A")).strip() or "N/A",
                    "specs": str(item.get("specs", "N/A")).strip() or "N/A",
                    "method": "qwen_ai_fallback",
                }
            )
        return cleaned
