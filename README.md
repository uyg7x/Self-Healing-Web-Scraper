<div align="center">

# Self-Healing Web Scraper

### A resilient, learning web scraper that automatically adapts to website redesigns

When a site changes its HTML structure, the scraper tries a **five-strategy fallback cascade** and learns which ones work best — so you never lose data after a redesign.

<br>

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-success)
![Maintenance](https://img.shields.io/badge/Maintained-Yes-brightgreen)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?logo=streamlit&logoColor=white)
![AI](https://img.shields.io/badge/AI-Gemini%20Powered-8E75B2?logo=google&logoColor=white)

<br>

[Overview](#overview) &nbsp;&bull;&nbsp; [Features](#features) &nbsp;&bull;&nbsp; [Architecture](#architecture) &nbsp;&bull;&nbsp; [How It Works](#how-it-works) &nbsp;&bull;&nbsp; [Quick Start](#quick-start) &nbsp;&bull;&nbsp; [Demo Mode](#demo-mode) &nbsp;&bull;&nbsp; [Configuration](#configuration) &nbsp;&bull;&nbsp; [Dashboard](#dashboard) &nbsp;&bull;&nbsp; [Limitations](#limitations) &nbsp;&bull;&nbsp; [Roadmap](#roadmap) &nbsp;&bull;&nbsp; [Video Walkthroughs](#video-walkthroughs) &nbsp;&bull;&nbsp; [Credits](#credits)

</div>

---

<div align="center">

## Overview

</div>

**Self-Healing Web Scraper** is an end-to-end e-commerce price comparison engine that doesn't break when sites redesign themselves. Instead of one brittle CSS selector, it uses a layered strategy pipeline combined with a persistent memory system that promotes the strategies that actually work — and asks an LLM (Google Gemini) for help when nothing else does.

It ships with:

- A clean interactive CLI runner (`main.py`)
- A live Streamlit analytics dashboard (`dashboard.py`)
- A breakage simulator (`--demo` flag) that proves the cascade works
- One-command Docker deployment
- Email alerts, daily scheduling, SQLite history, CSV exports, INR conversion, and more.

> **TL;DR** — Scrape any product across multiple sites, get a CSV with prices in ₹, watch the scraper self-heal when sites change, and visualize everything in a dashboard.

---

<div align="center">

## Features

</div>

| Capability | Description |
|---|---|
| **5-Strategy Cascade** | JSON-LD → CSS → Regex → Fuzzy self-heal → LLM (Gemini) |
| **Self-Learning Memory** | Promotes successful selectors & strategies to priority for next run |
| **JSON-LD Auto-Detection** | Extracts Schema.org structured data — survives 90% of redesigns |
| **Dual Fetching** | `requests` for speed, `Playwright` Chromium for JS-heavy sites |
| **Smart Price Recovery** | Distinguishes selling price from MRP, picks the *real* deal price |
| **Relevance Scoring** | Multi-factor 0-100 score (exact, brand, category, fuzzy, length, accessory penalty) |
| **Garbage Filtering** | Rejects menu items, filters, buttons, and short junk text |
| **SQLite Database** | Full history with strategy used and self-healed flag |
| **LLM Fallback (Gemini)** | Last-resort semantic extraction that survives total redesigns |
| **Breakage Simulator** | `--demo` mode intentionally breaks CSS to showcase the cascade |
| **Streamlit Dashboard** | Live charts, KPIs, and per-site / per-method breakdowns |
| **Docker Ready** | One-command `docker compose up` brings the dashboard online |
| **Email Alerts** | SMTP notifications on failure with diagnostic details |
| **Daily Scheduler** | Built-in 9 AM scheduler using the `schedule` library |
| **Currency Normalization** | All prices converted to INR before CSV export |
| **Stealth Headers** | Realistic browser headers to bypass basic 403 blocks |
| **Retries & Backoff** | Exponential backoff with rotation, encoding detection |

---

<div align="center">

## Architecture

</div>

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
+------------------------------------------------------------+
|  For Each Site:                                           |
|  1. Build search URL                                      |
|  2. Fetch page (requests OR Playwright)                   |
|  3. Run extraction cascade (5 strategies)                 |
|     a. JSON-LD  ->  b. CSS  ->  c. Regex                  |
|     ->  d. Fuzzy self-heal  ->  e. LLM (Gemini)           |
|  4. Validate & score relevance                            |
|  5. Recover real selling price                            |
|  6. Save to SQLite + CSV                                  |
|  7. Update self-healing memory                            |
+------------------------------------------------------------+
           |
           v
+----------------------+        +----------------------+
|  Generate CSV        |        |  Streamlit Dashboard |
|  (data/*.csv)        |        |  (dashboard.py)      |
+----------------------+        +----------------------+
```

### Module Map

```
+----------+        +-----------------+        +---------------+
| main.py  | -----> | scraper_engine  | -----> | self_healing  |
+----------+        +-----------------+        +---------------+
       |                  |   |   |                  |
       |                  |   |   +-----> llm_healer
       |                  |   |
       |                  |   +-----> validators (RelevanceScorer)
       |                  |
       |                  +-----> config (SITES_CONFIG)
       |
       +-----> database (SQLite)
       +-----> alerts (SMTP)
       +-----> scheduler (daily cron)
       +-----> dashboard (Streamlit / Plotly)
```

---

<div align="center">

## How It Works

</div>

### The 5-Strategy Cascade (tried in order)

```
+----------------------+
|  Strategy 0: JSON-LD |  -- Parses <script type="application/ld+json">
|                      |  -- Extracts Schema.org Product data
|                      |  -- MOST resilient to redesigns
+----------+-----------+
           | fail
           v
+----------------------+
|  Strategy 1: CSS     |  -- Tries each selector from config in order
|                      |  -- Fastest when classes haven't changed
+----------+-----------+
           | fail
           v
+----------------------+
|  Strategy 2: Regex   |  -- Pattern matching on raw HTML
|                      |  -- Catches products even when CSS is broken
+----------+-----------+
           | fail
           v
+----------------------+
|  Strategy 3: Fuzzy   |  -- Finds price symbols (Rs., INR, $, etc.)
|       Self-Heal      |  -- Scores nearby text blocks
|                      |  -- Uses difflib for fuzzy match
+----------+-----------+
           | fail
           v
+----------------------+
|  Strategy 4: LLM     |  -- Sends cleaned HTML to Google Gemini
|     (Gemini AI)      |  -- AI extracts product data semantically
|                      |  -- Survives TOTAL site redesigns
+----------------------+
```

### Self-Healing Memory

The first time a site is scraped, the engine walks the cascade and discovers which strategy works. On every subsequent run, that successful strategy is **promoted to the front of the queue** so the scraper gets faster with every use.

```
Run #1 (First time):
  Try Strategy 0 (JSON-LD)       -> FAIL (no structured data)
  Try Strategy 1 (CSS)           -> FAIL (class renamed)
  Try Strategy 2 (Regex)         -> FAIL (pattern changed)
  Try Strategy 3 (Fuzzy)         -> SUCCESS! Found 15 products
  Save to history: best_method = "self_healing"

Run #2 (Next day):
  Check history: best_method = "self_healing"
  Try Strategy 3 (Fuzzy) FIRST   -> SUCCESS in 2 seconds
  Time saved: ~10 seconds
```

### Smart Price Recovery

JSON-LD often returns the **MRP** instead of the actual selling price. The engine's price recovery module finds the *real* price by scanning the raw HTML around each product link and picking the lowest non-struck-through price.

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

### Relevance Scoring

Every extracted product is scored `0-100` before it's saved. The `RelevanceScorer` checks exact phrase match (+50), keyword overlap (+10/word), brand match (+30), category match (+20), fuzzy similarity (+0-15), length appropriateness, and applies an accessory penalty (-40) when the user isn't searching for accessories.

Products below the `40` threshold are dropped — so a search for "iPhone 15" won't return a thousand iPhone cases, cables, and chargers.

---

<div align="center">

## Quick Start

</div>

### Prerequisites

- **Python 3.10+**
- `pip` package manager
- Git (for cloning)
- A free **Google Gemini API key** (only needed for the LLM fallback strategy) — get one at [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

### Installation

```bash
# Clone the repository
git clone https://github.com/uyg7x/Self-Healing-Scraping-.git
cd self_healing_scraper

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright's Chromium browser
playwright install chromium
```

### Configure Gemini (optional, but recommended)

The scraper works without Gemini — the first 4 strategies cover most cases. To enable the LLM fallback, set your API key in a `.env` file at the project root:

```env
GEMINI_API_KEY=AIzaSy...your_key_here
```

> **Note:** `.env` is already in `.gitignore` so your key stays private.

### Usage

```bash
# Interactive scraper — searches a product across all configured sites
python main.py

# Breakage simulator — scrambles CSS to demo the self-healing cascade
python main.py --demo

# Streamlit analytics dashboard
streamlit run dashboard.py

# One-command Docker deployment (runs the dashboard on :8501)
docker compose up --build
```

### Example Session

```
============================================================
  SELF-HEALING E-COMMERCE PRICE COMPARATOR
============================================================
  REALITY CHECK: Amazon, Flipkart & friends have heavy
  anti-bot systems. If they fail, that is NORMAL.
  Robu.in, Sapna Online & BooksToScrape usually work.
============================================================

  Enter the product you want to search for: arduino uno

  Searching 'arduino uno' across 4 platforms...

  Searching Robu.in...
     [OK] 12 product(s) from: Robu.in • CSS selector

  Searching Books to Scrape (Practice)...
     [OK] 8 product(s) from: Books to Scrape (Practice) • JSON-LD

  ...

  SUCCESS! Saved 28 items total.
  CSV saved at: data/price_comparison_arduino_uno_20260817_194331.csv
```

The CSV is timestamped and written to `data/`. The dashboard reads from `data/scraper.db`.

---

<div align="center">

## Demo Mode

</div>

Add the `--demo` flag to **intentionally break every CSS selector** and watch the scraper self-heal in real time:

```bash
python main.py --demo
```

This simulates a complete site redesign. The console will show the cascade falling through each strategy until one succeeds:

```
  Searching Robu.in...
     [DEMO] Scrambling CSS selectors to simulate a site redesign...
     Trying JSON-LD structured data extraction... (fail)
     Trying selector strategy 1/1...                 (fail — broken)
     All traditional methods failed. Activating SELF-HEALING mode...
     SELF-HEALING SUCCEEDED! Found 12 products using intelligent matching
     [OK] 12 product(s) from: Robu.in • Self-healing (fuzzy match)
```

It's the fastest way to *see* the resilience working.

---

<div align="center">

## Dashboard

</div>

```bash
streamlit run dashboard.py
```

The dashboard reads `data/scraper.db` and shows:

- **KPI cards** — total products, sites scraped, min / max / average price, self-heal rate
- **Average price by website** (bar chart)
- **Extraction method distribution** (donut chart)
- **Daily scrape volume** (line chart)
- **Price per method** (box plot)
- **Top sellers** (table)
- **Self-healing memory viewer** (raw JSON of the strategy history)
- **Filterable data explorer** with search, site filter, method filter, date range, and "show only self-healed" toggle

Refresh the data with the sidebar button — cache auto-expires every 30 seconds.

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

Set `js_required=True` to make the engine use the **Playwright** browser instead of fast HTTP requests.

### Currency Conversion

Default rates in `config.py`:

```python
CURRENCY_TO_INR = {
    "INR": 1.0,
    "USD": 88.0,
    "GBP": 112.0,
}
```

All scraped prices are converted to INR before the CSV is written.

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

You'll receive an email every time a site fails to scrape.

### Daily Scheduler

```bash
# Runs the scraper every day at 09:00 (set in config.SCHEDULE_TIME)
python scheduler.py
```

---

<div align="center">

## File Documentation

</div>

```
self_healing_scraper/
+-- main.py              Interactive CLI runner (with --demo flag)
+-- dashboard.py         Streamlit analytics dashboard
+-- scraper_engine.py    5-strategy extraction pipeline
+-- self_healing.py      Selector learning and memory system
+-- validators.py        Relevance scoring and garbage filtering
+-- llm_healer.py        Google Gemini LLM fallback
+-- database.py          SQLite storage
+-- alerts.py            Email notifications
+-- scheduler.py         Daily scheduler
+-- config.py            Site configs and constants
+-- requirements.txt     Python dependencies
+-- Dockerfile           Container build config
+-- docker-compose.yml   One-command deployment
+-- LICENSE              MIT License
+-- README.md            This file
+-- data/                Output folder (gitignored)
   +-- scraper.db
   +-- selector_history.json
   +-- scraper.log
   +-- price_comparison_*.csv
```

### Module-by-Module

**`main.py` — The Entry Point**

The file you run. Handles user interaction, orchestrates every other module, and writes the final CSV.

- Sets up logging to file + console
- Shows a welcome banner explaining the limitations
- Accepts product search input
- Loops through every configured site
- Calls engine → validator → database → self-healing
- Converts all prices to INR
- Writes a timestamped CSV with per-source breakdown

**`scraper_engine.py` — The Heart**

The most complex file. Contains the actual scraping logic and the 5-strategy fallback pipeline.

- Fetches pages with `requests` (fast) or `Playwright` (real browser)
- Runs JSON-LD → CSS → Regex → Fuzzy → LLM in order
- Includes smart price recovery (MRP vs selling price)
- Exponential backoff retries
- Rotating User-Agent strings
- Stealth headers to bypass basic 403 blocks

**`self_healing.py` — The Memory System**

Tracks which strategies work and promotes successful ones to priority. This is the "brain" that makes the scraper smarter over time.

- Loads/saves `data/selector_history.json`
- Reorders CSS selectors based on past success rates
- Records which strategy worked for each site
- Tracks the last 10 failures per site
- `get_site_health()` returns success / failure stats

**`validators.py` — The Garbage Collector**

Filters out junk data so only clean, valid products end up in your CSV and database.

- `GARBAGE_WORDS` — menu items, filters, button text
- `ACCESSORY_WORDS` — penalizes iPhone cases when you searched "iPhone"
- `RelevanceScorer` — multi-factor 0-100 score with brand, category, fuzzy logic
- Detects Amazon-specific block text
- Cleans HTML entities (`&amp;` → `&`)
- Removes invisible Unicode and extra whitespace

**`llm_healer.py` — The AI Backup**

Wraps Google Gemini as the 5th and final fallback.

- Lazy SDK import (works even if `google-generativeai` is uninstalled)
- Defensive JSON parsing — handles markdown fences, prose, and malformed replies
- Strips `<script>` / `<style>` / HTML comments before sending
- Truncates HTML to stay under free-tier token limits
- **Never raises** — returns `[]` on any error

**`database.py` — The Storage Layer**

SQLite-backed persistent storage.

- `products` table with site, timestamp, method, self-healed flag
- Insert products with full metadata
- `close()` for graceful shutdown

**`config.py` — The Configuration**

All site-specific settings, currency rates, and User-Agent strings.

- `SITES_CONFIG` — all supported websites
- `CURRENCY_TO_INR` — FX rates
- `GEMINI_API_KEY` / `GEMINI_MODEL` — LLM settings
- `EMAIL_CONFIG`, `SCHEDULE_TIME`, `PROXY_CONFIG`, `VALIDATION_RULES`

**`dashboard.py` — The Analytics**

Streamlit + Plotly UI for inspecting scraper history.

- Cached data loaders (30s TTL)
- KPI cards (min / max / avg / count / heal rate)
- Per-site price chart, method distribution, daily volume, price-by-method box plot
- Filterable data explorer and self-healing memory viewer

**`alerts.py` — The Notifier**

SMTP email alerts on failure.

- Connects to Gmail by default (configurable)
- Sends formatted email with site, timestamp, error, retry count
- Includes troubleshooting steps in the body

**`scheduler.py` — The Automation**

Daily scheduler.

- Uses the `schedule` library
- Default 9:00 AM run (configurable)
- `run_now()` for immediate testing

---

<div align="center">

## Limitations

</div>

### Sites That WILL Work

- `books.toscrape.com` — practice site, no anti-bot
- `robu.in` — simple Indian e-commerce
- Any site with **JSON-LD** structured data
- Most static HTML sites without Cloudflare / Akamai

### Sites That MIGHT Work

- Sites with moderate anti-bot (with Playwright + delays)
- Sites that allow browser automation

### Sites That WILL NOT Work

- `amazon.in` and `flipkart.com` — aggressive bot detection (CAPTCHA, fingerprinting)
- Pure JavaScript SPAs that return empty HTML to scrapers
- Sites rendering prices in `<canvas>`
- API-only content with no HTML

### Why Modern Sites Block Scrapers

- CAPTCHA challenges (visual and behavioral)
- IP reputation checks (datacenter IP blocking)
- Browser fingerprinting (canvas, WebGL, fonts, plugins)
- Behavioral analysis (mouse, scroll, timing)
- Device sensor data (mobile)

If a site fails, the scraper will offer to ask **Gemini** for help — and you can re-try via the LLM fallback.

---

<div align="center">

## Roadmap

</div>

- [x] JSON-LD auto-detection
- [x] Expanded price patterns (Rs., INR, USD, EUR)
- [x] Smart MRP vs selling price detection
- [x] Price recovery from raw HTML
- [x] LLM-powered fallback (Gemini Flash)
- [x] Relevance scoring and smart filtering
- [x] Streamlit live dashboard
- [x] Breakage simulator (demo mode)
- [x] Docker containerization
- [x] Self-healing memory persistence
- [x] Per-source CSV designation column
- [ ] Visual diff tool (before and after redesign)
- [ ] Multi-language support (Hindi and English)
- [ ] Slack and Discord webhook alerts
- [ ] PyPI package release
- [ ] Distributed scraping with Celery
- [ ] Proxy rotation marketplace integration

---

<div align="center">

## Video Walkthroughs

</div>

We made two video walkthroughs that explain how the scraper is built, how the self-healing cascade works, and how to deploy it. Watch them if you want a guided tour of the code.

| Video | What it covers |
|---|---|
| [Project Overview & Architecture](https://www.youtube.com/watch?v=H4Lns2pkIjk) | High-level walkthrough of the 5-strategy cascade, the self-healing memory system, and how every module fits together. |
| [Live Demo & Deployment](https://www.youtube.com/watch?v=YC9gpcwqe3U) | Running the scraper in demo mode, watching the cascade in action, and deploying the dashboard with Docker. |

---

<div align="center">

## License

</div>

This project is released under the **MIT License** — see [LICENSE](LICENSE) for details.

---

<div align="center">

## Credits

</div>

**Built with care by**

# PJY & team RuST

> *Dharmendra and the RuST team — Resilient Scraping Toolkit.*
> *Built so that the next redesign doesn't break your data.*

Special thanks to the open-source community: `BeautifulSoup`, `Playwright`, `Streamlit`, `Plotly`, `Pandas`, `Requests`, and of course **Google Gemini** for powering the last-resort LLM fallback.

---

<div align="center">

If this project saved you time, a star on the repo is always appreciated.

[Back to top](#self-healing-web-scraper)

</div>
