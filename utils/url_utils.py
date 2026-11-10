import hashlib
import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


TRACKING_PARAMS = {
    "tag", "ref", "ref_", "pd_rd_r", "pd_rd_w", "pd_rd_wg",
    "pf_rd_p", "pf_rd_r", "psc", "th", "sr", "qid", "sprefix",
    "crid", "dib", "dib_tag", "content-id", "smid", "source",
    "utm_source", "utm_medium", "utm_campaign", "utm_term",
    "gclid", "fbclid", "affid", "affiliate",
}


def normalize_url(url: str) -> str:
   
    if not url or url == "N/A":
        return ""

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return url

    p = urlparse(url)
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    query = [(k, v) for k, v in parse_qsl(p.query) if k.lower() not in TRACKING_PARAMS]
    query.sort()

    path = p.path.rstrip("/") or "/"

    return urlunparse(
        (p.scheme.lower(), host, path, "", urlencode(query), "")
    )


def content_fingerprint(product: dict) -> str:
   
    name = (product.get("name") or "").lower().strip()
    name = re.sub(r"\s+", " ", name)
    name = re.sub(r"[^\w\s]", "", name)

    price = product.get("price_float")
    price_str = f"{price:.2f}" if isinstance(price, (int, float)) else ""

    raw = f"{name}|{price_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def is_challenge_html(html: str) -> bool:
  
    if not html or len(html) < 200:
        return True

    lowered = html[:8000].lower()

    markers = (
        "cf-chl", "cf_chl_opt", "challenge-platform",
        "captcha-delivery", "px-captcha", "_incapsula_resource",
        "please verify you are a human", "robot check",
        "access denied", "request blocked",
        "unusual traffic from your computer",
    )
    return any(m in lowered for m in markers)