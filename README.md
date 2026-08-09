<div align="center">

# Self-Healing  Scraper

### A resilient web scraper that automatically adapts to website redesigns

When a site changes its HTML structure, the scraper tries **four fallback strategies** and learns which ones work best -- so you never lose data after a redesign.

<br>

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-success)
![Maintenance](https://img.shields.io/badge/Maintained-Yes-brightgreen)

<br>

[Quick Start](#quick-start) &nbsp;&bull;&nbsp; [Features](#features) &nbsp;&bull;&nbsp; [Architecture](#architecture) &nbsp;&bull;&nbsp; [How It Works](#how-it-works) &nbsp;&bull;&nbsp; [File Documentation](#file-documentation) &nbsp;&bull;&nbsp; [Roadmap](#roadmap)

</div>

---

<div align="center">

## Features

</div>

| Capability | Description |
|---|---|
| JSON-LD Auto-Detection | Extracts structured data that survives 90 percent of redesigns |
| Self-Healing Selectors | Tries CSS then Regex then Fuzzy fallback chain |
| Dual Fetching | Simple HTTP requests plus Playwright browser automation |
| Data Validation | Rejects garbage data, checks quality scores |
| SQLite Database | Structured storage with full history |
| Self-Learning | Promotes successful selectors to priority |
| CSV Export | Per-search timestamped comparison files |
| Multi-Currency | Auto-converts USD, GBP, and INR prices |
| Email Alerts | Notifications on scraping failures |
| Daily Scheduler | Runs automatically at 9 AM |

---

<div align="center">

## Architecture

</div>

<div align="center">

```
+----------------------+
|   User Input         |
|   python main.py     |
+----------+-----------+
           |
           v
+----------------------+
|  Load Configuration  |
|  (config.py)         |
+----------+-----------+
           |
           v
+----------------------+
|  For Each Site:      |
|  1. Build URL        |
|  2. Fetch Page       |
|  3. Extract Data     |
|  4. Validate         |
|  5. Save to DB       |
|  6. Update Memory    |
+----------+-----------+
           |
           v
+----------------------+
|  Generate CSV        |
|  Print Results       |
+----------------------+
```

</div>

---

<div align="center">

## How It Works

</div>

### Extraction Strategy (Tried in Order)

```
Strategy 1: JSON-LD
  └── Parses <script type="application/ld+json">
  └── Extracts @type="Product" data
  └── Most resilient to CSS/HTML redesigns

Strategy 2: CSS Selectors
  └── Tries each selector from config in order
  └── Fastest when CSS classes haven't changed

Strategy 3: Regex Fallback
  └── Pattern matching on raw HTML
  └── Catches products even when CSS is broken

Strategy 4: Fuzzy Self-Healing
  └── Finds price symbols (Rs., INR, $, etc.)
  └── Scores nearby text blocks
  └── Last resort when everything else fails
```

### Self-Healing Memory

```
Run #1 (First time):
  Try Strategy 1 (JSON-LD)       -> FAIL (no structured data)
  Try Strategy 2 (CSS)           -> FAIL (class renamed)
  Try Strategy 3 (Regex)         -> FAIL (pattern changed)
  Try Strategy 4 (Fuzzy)         -> SUCCESS! Found 15 products
  Save to history: best_method = "fuzzy"

Run #2 (Next day):
  Check history: best_method = "fuzzy"
  Try Strategy 4 (Fuzzy) FIRST   -> SUCCESS in 2 seconds
  Time saved: ~10 seconds
```

### Price Recovery

```
Step 1: JSON-LD extracts price "Rs. 4,000" (often the MRP)
        |
        v
Step 2: Check 1500-char window AFTER product link
        |
        v
Step 3: Find lowest non-struck-through price "Rs. 3,599"
        |
        v
Step 4: If MRP is more than 5% higher, replace with selling price
        |
        v
Final: Real selling price (matches the product page)
```

---

<div align="center">

## File Documentation

</div>

### Project Structure

```
self_healing_scraper/
+-- main.py              Interactive CLI runner
+-- scraper_engine.py    4-strategy extraction pipeline
+-- self_healing.py      Selector learning and memory system
+-- validators.py        Data quality and garbage filtering
+-- database.py          SQLite storage
+-- alerts.py            Email notifications
+-- scheduler.py         Daily scheduler
+-- config.py            Site configs and constants
+-- requirements.txt     Python dependencies
+-- .gitignore           Excludes data/, venv/, etc.
+-- LICENSE              MIT License
+-- data/                Output folder (gitignored)
   +-- scraper.db
   +-- selector_history.json
   +-- price_comparison_*.csv
```

### File-by-File Explanation

<br>

**main.py -- The Entry Point**

This is the file you run. It handles user interaction, orchestrates all other modules, and produces the final CSV output.

What it does:
- Sets up logging to both file and console
- Shows a welcome banner explaining limitations
- Accepts product search input from the user
- Loops through each configured website
- Calls the scraper engine, validator, database, and self-healing system
- Converts all prices to Indian Rupees
- Generates a timestamped CSV file with comparison results

<br>

**scraper_engine.py -- The Heart of the Project**

This file contains all the actual scraping logic and the four-strategy fallback pipeline. It is the most complex and important file.

What it does:
- Fetches web pages using either `requests` (fast HTTP) or `Playwright` (real browser)
- Tries four extraction strategies in order:
  1. JSON-LD structured data extraction
  2. CSS selector matching
  3. Regex pattern matching
  4. Fuzzy self-healing with price symbol scoring
- Includes a smart price recovery function that distinguishes MRP from selling prices
- Handles retries with exponential backoff
- Rotates User-Agent strings to avoid basic blocking
    <img width="1664" height="928" alt="1786279645" src="https://github.com/user-attachments/assets/d615b438-7877-4137-9024-a9008291cac2" />

<br>

**self_healing.py -- The Memory System**

This file tracks which extraction strategies work for each site and promotes successful ones to priority. It is the "brain" that makes the scraper smarter over time.

What it does:
- Loads and saves selector history to `data/selector_history.json`
- Reorders CSS selectors based on past success rates
- Records which strategy (JSON-LD, CSS, regex, fuzzy) worked for each site
- Tracks failure history (keeps last 10 failures per site)
- Provides `get_site_health()` to check scraping statistics
- Promotes frequently-successful strategies to be tried first

<img width="1664" height="928" alt="1786279483" src="https://github.com/user-attachments/assets/274e63b6-b747-462c-85b6-824748105f66" />

<br>

**validators.py -- The Garbage Collector**

This file filters out junk data so only clean, valid products end up in your CSV and database.

What it does:
- Maintains a `GARBAGE_WORDS` list (menu items, filters, button text)
- Checks if product names are too short (likely menu items)
- Checks if prices are suspiciously low (likely accessories, not complete products)
- Detects Amazon-specific block text
- Cleans HTML entities (`&amp;` becomes `&`)
- Removes invisible Unicode characters
- Strips extra whitespace

<br>

**database.py -- The Storage Layer**

This file manages SQLite database operations for persistent storage of all scraped products.

What it does:
- Creates the `products` table on first run
- Inserts scraped products with metadata (site, timestamp, method)
- Stores product name, price, price_float, price_inr, link, and specs
- Tracks which extraction method was used
- Provides `close()` for graceful shutdown

<br>

**config.py -- The Configuration**

This file holds all site-specific settings, currency conversion rates, and User-Agent strings.

What it does:
- Defines `SITES_CONFIG` dictionary with all supported websites
- Specifies selectors, regex patterns, and JS requirements per site
- Configures currency conversion rates (INR, USD, GBP)
- Sets retry counts, timeouts, and delays
- Defines proxy and email alert settings
- Specifies scheduler time (default 9:00 AM)

<br>

**alerts.py -- The Notifier**

This file handles email notifications when scraping fails.

What it does:
- Connects to SMTP server (default Gmail)
- Sends formatted email with error details
- Includes site name, timestamp, error message, and retry count
- Only sends if `EMAIL_CONFIG.enabled = True` in config
- Provides troubleshooting steps in the email body

<br>

**scheduler.py -- The Automation**

This file runs the scraper automatically at a scheduled time each day.

What it does:
- Uses the `schedule` library to trigger jobs at 9:00 AM daily
- Runs in an infinite loop checking every minute
- Can be started with `scheduler.start()` for background operation
- Can be stopped with `scheduler.stop()` or Ctrl+C
- Supports `run_now()` for immediate testing

---[mermaid-diagram-1786274969537.pdf](https://github.com/user-attachments/files/30873294/mermaid-diagram-1786274969537.pdf)

<div align="center">

## Quick Start

</div>

### Prerequisites

- Python 3.10 or higher
- pip package manager
- Git (for cloning)

### Installation

```bash
# Clone the repository
git clone https://github.com/uyg7x/Self-Healing-Scraping-.git
cd self_healing_scraper

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### Usage

```bash
# Run the interactive scraper
python main.py
```

### Example Session

```
============================================================
SELF-HEALING E-COMMERCE PRICE COMPARATOR (v3)
============================================================
REALITY CHECK: Amazon, Flipkart, Ajio, Meesho, ShopClues,
GlowRoad and Goodreads have heavy anti-bot systems. If they fail,
that is NORMAL. Robu.in, Sapna Online and BooksToScrape usually work.
============================================================

Enter the product you want to search for: arduino uno

Searching 'arduino uno' across 4 platforms...
```

The output CSV is saved to `data/price_comparison_<query>_<timestamp>.csv`.

---

<div align="center">

## Configuration

</div>

### Adding a New Site

Edit [config.py](config.py) and add a new entry to `SITES_CONFIG`:

```python
"my_site": {
    "name": "My E-Commerce Site",
    "url": "https://example.com",
    "base_search_url": "https://example.com/search?q={query}",
    "js_required": False,
    "currency": "INR",
    "selectors": [
        {"product_name": "h2.product-title",
         "price": "span.price",
         "specs": "div.specs"}
    ],
    "regex_fallback": {
        "product_name": r'<h2[^>]*class="product-title"[^>]*>([^<]+)</h2>',
        "price": r'Rs\.?\s*([\d,]+)'
    }
}
```

### Currency Conversion

Default rates in `config.py`:

```python
CURRENCY_TO_INR = {
    "INR": 1.0,
    "USD": 88.0,
    "GBP": 112.0,
}
```

### Email Alerts

Enable in `config.py`:

```python
EMAIL_CONFIG = {
    "enabled": True,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "email": "your-email@gmail.com",
    "password": "your-app-password",
    "recipient": "alerts@example.com"
}
```

---

<div align="center">

## Important Limitations

</div>

### Sites That WILL Work

- books.toscrape.com (practice site, no anti-bot)
- robu.in (simple Indian e-commerce)
- Any site with JSON-LD structured data
- Most static HTML sites without Cloudflare/Akamai protection

### Sites That MIGHT Work

- Sites with moderate anti-bot (VijaySales, Meesho with delays)
- Sites that allow Playwright browser automation

### Sites That WILL NOT Work

- amazon.in and flipkart.com -- Aggressive bot detection with CAPTCHA and fingerprinting
- Pure JavaScript-rendered SPAs that return empty HTML to scrapers
- Sites using image-based prices (canvas rendering)
- Sites with API-only content (no HTML to scrape)

### Why These Sites Block Scrapers

Modern e-commerce sites use:
- CAPTCHA challenges (visual and behavioral tests)
- IP reputation checks (blocking datacenter IPs)
- Browser fingerprinting (canvas, WebGL, fonts, plugins)
- Behavioral analysis (mouse movement, scroll patterns)
- Network timing analysis
- Device sensor data (mobile)

---

<div align="center">

## Roadmap

</div>

- [x] JSON-LD auto-detection
- [x] Expanded price patterns (Rs., INR, USD, EUR)
- [x] Smart MRP vs selling price detection
- [x] Price recovery from raw HTML
- [x] Hinglish code comments for readability
- [ ] LLM-powered fallback (Gemini Flash or Ollama)
- [ ] Streamlit live dashboard
- [ ] Visual diff tool (before and after redesign)
- [ ] Multi-language support (Hindi and English)
- [ ] Slack and Discord webhook alerts
- [ ] Confidence scoring per product
- [ ] Docker containerization
- [ ] PyPI package release

---

<div align="center">

## Tech Stack

</div>

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| HTML Parsing | BeautifulSoup4 with lxml backend |
| HTTP Requests | requests library with retry logic |
| Browser Automation | Playwright (Chromium) |
| Database | SQLite3 (built-in) |
| Scheduling | schedule library |
| Logging | Python logging module |

---



## License

</div>

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

<div align="center">

## Acknowledgments

</div>

- BeautifulSoup4 for robust HTML parsing
- Playwright team for browser automation
- The open-source community for inspiration
- Everyone who reported issues and contributed fixes

---

<div align="center">

### Built for resilience. Designed to adapt. Made for hackers.

<br>

**Star this repository if it helped you**

</div>
