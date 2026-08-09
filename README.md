# 🤖 Self-Healing Scraper

A resilient web scraper that automatically adapts to website redesigns. When a site changes its HTML structure, the scraper tries **4 fallback strategies** and learns which ones work best — so you never lose data after a redesign.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-success)

---

## ✨ Features

| Feature | Description |
|---|---|
| 🏷️ **JSON-LD Auto-Detection** | Extracts structured data (survives 90% of redesigns) |
| 🔄 **Self-Healing Selectors** | Tries CSS → Regex → Fuzzy fallback chain |
| 🎭 **Dual Fetching** | Simple HTTP requests + Playwright browser automation |
| ✅ **Data Validation** | Rejects garbage data, checks quality scores |
| 💾 **SQLite Database** | Structured storage with full history |
| 🧠 **Self-Learning** | Promotes successful selectors to priority |
| 📊 **CSV Export** | Per-search timestamped comparison files |
| 💱 **Multi-Currency** | Auto-converts USD/GBP/INR prices |
| 📧 **Email Alerts** | Notifications on scraping failures |
| ⏰ **Daily Scheduler** | Runs automatically at 9 AM |

---

## 🛡️ Extraction Strategy (Tried in Order)

```
1. JSON-LD          → Schema.org structured data (most resilient)
2. CSS Selectors    → Plan A from config
3. Regex Fallback   → Pattern matching on HTML
4. Fuzzy Self-Healing → AI-style matching when everything else fails
```

When a site redesigns:
- ✅ CSS class renames → recovered via Regex/Fuzzy
- ✅ Tag swaps (`span` → `div`) → recovered via Fuzzy
- ✅ Price format changes (₹ → Rs.) → recovered via Fuzzy
- ✅ Complete CSS overhaul (if JSON-LD exists) → recovered via JSON-LD
- ❌ Anti-bot blocks (CAPTCHA/403) → requires paid solutions
- ❌ Pure JS SPAs with empty HTML → requires API reverse-engineering

---

## 🚀 Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Run the scraper
```bash
python main.py
```

### 3. Enter a product to search
```
🔍 Enter the product you want to search for: arduino uno
```

Output: `data/price_comparison_arduino_uno_20260809_143022.csv`

---

## 📁 Project Structure

```
self_healing_scraper/
├── main.py              # Interactive CLI runner
├── scraper_engine.py    # 4-strategy extraction pipeline
├── self_healing.py      # Selector learning/memory system
├── validators.py        # Data quality + garbage filtering
├── database.py          # SQLite storage
├── alerts.py            # Email notifications
├── scheduler.py         # Daily scheduler
├── config.py            # Site configs + constants
├── requirements.txt     # Dependencies
├── .gitignore           # Excludes data/, venv/, etc.
├── LICENSE              # MIT
└── data/                # Output folder (gitignored)
    ├── scraper.db
    ├── selector_history.json
    └── price_comparison_*.csv
```

---

## 🔧 Configuration

Edit [config.py](config.py) to add/modify sites:

```python
SITES_CONFIG = {
    "robu": {
        "name": "Robu.in",
        "base_search_url": "https://robu.in/?s={query}",
        "js_required": False,
        "currency": "INR",
        "selectors": [{"product_name": "...", "price": "..."}],
        "regex_fallback": {"product_name": r"...", "price": r"..."},
    },
    # Add more sites...
}
```

---

## ⚠️ Important Limitations

### Sites That WILL Work
- ✅ `books.toscrape.com` (practice site)
- ✅ `robu.in` (simple Indian e-commerce)
- ✅ Sites with JSON-LD structured data

### Sites That MIGHT Work
- ⚠️ Sites with moderate anti-bot (VijaySales, Meesho with delays)

### Sites That WILL NOT Work
- ❌ `amazon.in` / `flipkart.com` — Aggressive bot detection (CAPTCHA + fingerprinting)
- ❌ Pure JS-rendered SPAs returning empty HTML
- ❌ Image-based prices (canvas-rendered)

---

## 🗺️ Roadmap

- [x] JSON-LD auto-detection
- [x] Expanded price patterns (₹, Rs., INR, USD, €)
- [ ] 🤖 LLM-powered fallback (Gemini Flash / Ollama)
- [ ] 📊 Streamlit live dashboard
- [ ] 🔍 Visual diff tool (before/after redesign)
- [ ] 🌐 Multi-language support (Hindi/English)
- [ ] 📱 Slack/Discord webhook alerts
- [ ] 🎯 Confidence scoring per product

---

## 📜 License

MIT — see [LICENSE](LICENSE)

## 🤝 Contributing

Pull requests welcome. For major changes, open an issue first.