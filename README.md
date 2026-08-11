# Self-Healing Scraper

### A resilient web scraper that automatically adapts to website redesigns, with an LLM (Google Gemini) fallback for the hardest pages.

When a site changes its HTML structure, the scraper walks through **five extraction strategies** in order, learns which ones work best, and tags every result with a `Source` showing exactly which platform and which strategy produced it. The LLM step is opt-in per site so you stay in control of your API quota.

<br>

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-success)
![Maintenance](https://img.shields.io/badge/Maintained-Yes-brightgreen)

<br>

[Quick Start](#quick-start) &nbsp;&bull;&nbsp; [Demo](#demo) &nbsp;&bull;&nbsp; [Features](#features) &nbsp;&bull;&nbsp; [Architecture](#architecture) &nbsp;&bull;&nbsp; [How It Works](#how-it-works) &nbsp;&bull;&nbsp; [File Documentation](#file-documentation) &nbsp;&bull;&nbsp; [Roadmap](#roadmap)

---

<div align="center">

## Demo

</div>

### Screenshots

> Drop your screenshot files into `docs/screenshots/` using these exact filenames, then the images will show up here automatically.

<br>

**Terminal run showing all 5 strategies and the LLM opt-in prompt:**

<!-- TODO: Drop your terminal screenshot here as docs/screenshots/terminal-run.png -->
<p align="center">
  <img src="docs/screenshots/terminal-run.png" alt="Terminal run showing all 5 strategies" width="900"/>
  <br/>
  <sub><i>Replace this image by saving your screenshot as <code>docs/screenshots/terminal-run.png</code></i></sub>
</p>

<br>

**Generated CSV with the Source designation column:**

<!-- TODO: Drop your CSV / spreadsheet screenshot here as docs/screenshots/csv-output.png -->
<p align="center">
  <img src="docs/screenshots/csv-output.png" alt="CSV output with Source column" width="900"/>
  <br/>
  <sub><i>Replace this image by saving your screenshot as <code>docs/screenshots/csv-output.png</code></i></sub>
</p>

<br>

**Architecture / strategy flow diagram:**

<!-- TODO: Drop your architecture diagram here as docs/screenshots/architecture.png -->
<p align="center">
  <img src="docs/screenshots/architecture.png" alt="Architecture diagram" width="900"/>
  <br/>
  <sub><i>Replace this image by saving your diagram as <code>docs/screenshots/architecture.png</code></i></sub>
</p>

<br>

### Video walkthrough

> Add your YouTube link below. Replace `YOUR_VIDEO_ID` with the 11-character ID from the YouTube URL (the part after `v=`).

<br>

<!-- TODO: Replace YOUR_VIDEO_ID with your actual YouTube video ID -->
<p align="center">
  <a href="https://www.youtube.com/watch?v=YOUR_VIDEO_ID">
    <img src="https://img.youtube.com/vi/YOUR_VIDEO_ID/0.jpg" alt="Watch the demo video" width="900"/>
  </a>
  <br/>
  <sub><i>Click the image above to watch the demo. To make it work: open this README, find the line that says <code>YOUR_VIDEO_ID</code>, and replace BOTH occurrences with the 11-character ID from your YouTube link.</i></sub>
</p>

---

## Features

| Capability | Description |
|---|---|
| JSON-LD auto-detection | Parses `<script type="application/ld+json">` blocks; survives most redesigns. |
| CSS selector extraction | Tries each configured selector in priority order. |
| Regex fallback | Pattern-matches raw HTML when CSS is broken. |
| Fuzzy self-healing | Finds price symbols, scores nearby text blocks, builds product guesses. |
| LLM (Gemini) fallback | Asks Google Gemini to read messy HTML when all four traditional methods fail. |
| Source designation | Every result is tagged with `Website - Strategy` in the terminal, logs, and CSV. |
| Opt-in AI mode | Gemini is only called when you answer `y` to a per-site prompt. |
| Dual fetching | `requests` for fast static pages, Playwright for JavaScript-rendered ones. |
| Smart price recovery | Distinguishes MRP from selling price; recovers missing prices from raw HTML. |
| Multi-currency | Auto-converts USD, GBP, and EUR into Indian Rupees. |
| Data validation | Rejects junk rows, scrapes, and bot-detection blocks. |
| SQLite history | Stores every result with timestamp and extraction method. |
| Self-learning | Promotes selectors and strategies that historically succeed. |
| CSV export | Per-search timestamped comparison file in `data/`. |
| Daily scheduler | Optional `scheduler.py` to run automatically at 09:00. |
| Email alerts | Optional failure notifications via SMTP. |

---

## Architecture

```
+------------------------------+
|  User input: search term     |
|  $ python main.py            |
+--------------+---------------+
               |
               v
+------------------------------+
|  Load config (config.py)     |
|  Build URL per site          |
+--------------+---------------+
               |
               v
+------------------------------+
|  Fetch page                  |
|  (requests or Playwright)    |
+--------------+---------------+
               |
               v
+------------------------------+
|  extract_data() pipeline     |
|                              |
|  1. JSON-LD                  |
|  2. CSS selector             |
|  3. Regex                    |
|  4. Fuzzy self-heal          |
|  5. LLM (Gemini) -- opt-in   |
+--------------+---------------+
               |
               v
+------------------------------+
|  Validate, save to DB,       |
|  update selector history     |
+--------------+---------------+
               |
               v
+------------------------------+
|  Export CSV, print summary   |
+------------------------------+
```

---

## How It Works

### Extraction strategy order

The five strategies are tried in this order. The first one that returns usable products wins.

1. **JSON-LD (structured data)**
   - Parses `<script type="application/ld+json">` blocks.
   - Reads `@type: "Product"` items, including nested `ItemList` and `Offer` data.
   - Most resilient because it is machine-readable metadata, not HTML.

2. **CSS selectors**
   - Tries each selector in `config.SITES_CONFIG[...]["selectors"]` in priority order.
   - Fastest when classes and IDs have not been renamed.

3. **Regex fallback**
   - Pattern-matches raw HTML using the regexes from `config.py`.
   - Catches products even when the site has no structured data.

4. **Fuzzy self-healing**
   - Scans for currency symbols (`Rs.`, `INR`, `$`, `EUR`, etc.).
   - Looks 500 characters before each price for a text block that "looks like" a product name.
   - Scores candidates by length, word choice, and capitalization.

5. **LLM fallback (Google Gemini) -- opt-in**
   - Only reached if strategies 1-4 all return zero products.
   - Sends a trimmed version of the HTML to `gemini-2.0-flash`.
   - Parses the JSON list Gemini returns and tags every product as `Gemini AI (LLM)`.
   - You are asked for confirmation in the terminal before it runs.

### Source designation

Every product ends up with a friendly source label, e.g.:

| Method | CSV / terminal label |
|---|---|
| `json_ld` | `Website Name - JSON-LD (structured data)` |
| `css_selector` | `Website Name - CSS selector` |
| `regex` | `Website Name - Regex fallback` |
| `self_healing` | `Website Name - Self-healing (fuzzy match)` |
| `llm` | `Website Name - Gemini AI (LLM)` |

The label appears in the terminal per site, in a summary at the end of the run, and as the first column of the output CSV.

### Self-healing memory

```
Run 1 (first time on a site)
  Strategy 1 (JSON-LD)  -> FAIL
  Strategy 2 (CSS)      -> FAIL
  Strategy 3 (Regex)    -> FAIL
  Strategy 4 (Fuzzy)    -> SUCCESS (15 products)
  Saved to data/selector_history.json

Run 2 (next time on the same site)
  Reads history -> "Fuzzy worked last time"
  Tries Strategy 4 first
  SUCCESS in 2 seconds
```

### Price recovery

```
Step 1: JSON-LD extracts "Rs. 4,000"  (often the MRP)
Step 2: Look 1500 chars AFTER the product link
Step 3: Find the lowest non-struck-through price "Rs. 3,599"
Step 4: If MRP is more than 5% higher, replace with the lower one
Result: Real selling price, matching the product page
```

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- `pip` package manager
- A Google Gemini API key (only needed if you want to use the LLM fallback; everything else works without one)

### Installation

```bash
git clone https://github.com/uyg7x/Self-Healing-Scraping-.git
cd self_healing_scraper

pip install -r requirements.txt
playwright install chromium
```

### Run

```bash
python main.py
```

You will be prompted for a product name. The scraper walks through every configured site, applies the four traditional strategies, and asks before invoking Gemini on any site where they all fail.

Output CSVs are saved as `data/price_comparison_<query>_<timestamp>.csv`.

---

## Configuration

### Adding a new site

Edit `config.py` and add an entry under `SITES_CONFIG`:

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

### Currency conversion

```python
CURRENCY_TO_INR = {
    "INR": 1.0,
    "USD": 88.0,
    "GBP": 112.0,
    "EUR": 95.0,
}
```

### Email alerts

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

### Daily scheduler

Set `SCHEDULE_TIME = "HH:MM"` in `config.py` and run `python scheduler.py` in the background.

---

## LLM Fallback (Google Gemini)

The 5th strategy uses Google's Gemini API to read messy HTML when nothing else works.

### How to get a free API key

1. Open https://aistudio.google.com/apikey
2. Sign in with any Google account.
3. Click **Create API key**.
4. Copy the key (it looks like `AIzaSy...`).

Free-tier limits on `gemini-2.0-flash` are 15 requests per minute and 1,500 per day -- plenty for this scraper.

### How to provide the key

The code reads the key in this order:

1. **Environment variable** (recommended):

   ```powershell
   # Windows PowerShell (current session)
   $env:GEMINI_API_KEY = "AIzaSy...your_key_here"

   # Or set it permanently: System Properties -> Environment Variables
   ```

2. **`.env` file at the project root** (also recommended, already gitignored):

   ```env
   GEMINI_API_KEY=AIzaSy...your_key_here
   ```

   A template is provided in `.env.example`.

### How the opt-in prompt works

When all four traditional strategies fail for a site, the scraper prints:

```
[WARN] No output found on Amazon India after 4 strategies.
No output found. Use LLM (Google Gemini) mode for Amazon India? [y/N]:
```

| You type | What happens |
|---|---|
| `y` + Enter | Gemini is called for that site only. Results tagged `Amazon India - Gemini AI (LLM)`. |
| `n` (or just Enter) | The site is skipped. No API call, no quota used. |

This happens **per site** -- you can pick exactly which blocked sites to retry with AI.

---

## Project Structure

```
self_healing_scraper/
|-- main.py                Interactive CLI runner
|-- scraper_engine.py      5-strategy extraction pipeline
|-- llm_healer.py          5th strategy: Google Gemini fallback
|-- self_healing.py        Selector learning and history
|-- validators.py          Data quality and garbage filtering
|-- database.py            SQLite storage
|-- alerts.py              Email notifications
|-- scheduler.py           Daily scheduler
|-- config.py              Site configs, currency, Gemini settings
|-- requirements.txt       Python dependencies
|-- LICENSE                MIT License
|-- README.md              This file
|-- .env.example           Template for local secrets (real .env is gitignored)
|-- docs/
|   |-- screenshots/       Drop your demo screenshots here
|-- data/                  Output folder (gitignored, created at runtime)
   |-- scraper.db
   |-- selector_history.json
   |-- scraper.log
   |-- price_comparison_*.csv
```

---

## File Documentation

### `main.py` -- the entry point

What it does:

- Sets up logging to file and console.
- Shows the welcome banner.
- Accepts a product search term from the user.
- Loops through every configured site, calls the scraper engine, validator, database, and self-healing system.
- Converts all prices to Indian Rupees.
- For sites where all four strategies fail, asks the user before calling Gemini.
- Generates a timestamped CSV with the `Source` designation column.

### `scraper_engine.py` -- the heart of the project

What it does:

- Fetches pages via `requests` (fast) or Playwright (real browser for JavaScript).
- Tries the five extraction strategies in order.
- Includes smart price recovery (MRP vs selling price).
- Exposes `extract_with_llm()` for the interactive AI prompt in `main.py`.
- Handles retries with exponential backoff and User-Agent rotation.

### `llm_healer.py` -- the Gemini fallback

What it does:

- Trims the HTML (removes `<script>`, `<style>`, comments; caps at 20,000 chars).
- Sends a strict prompt that asks Gemini for a JSON list `[{name, price, link}, ...]`.
- Strips ` ```json ` fences and extracts the first `[...]` block.
- Catches every exception and returns `[]` -- never crashes the scraper.
- Lazily imports `google-generativeai` so the rest of the app still runs without it.

### `self_healing.py` -- the memory system

What it does:

- Loads and saves selector history to `data/selector_history.json`.
- Reorders CSS selectors by past success rate.
- Records which strategy (JSON-LD, CSS, regex, fuzzy, LLM) worked for each site.
- Tracks the last 10 failures per site.
- Promotes frequently-successful strategies to be tried first.

### `validators.py` -- the garbage collector

What it does:

- Maintains a `GARBAGE_WORDS` list (menu items, filter text, button labels).
- Rejects product names that are too short or too long.
- Rejects suspicious prices (e.g. too low, missing digits).
- Detects Amazon-specific block text.
- Cleans HTML entities (`&amp;` -> `&`).
- Strips invisible Unicode characters.

### `database.py` -- the storage layer

What it does:

- Creates the `products` table on first run.
- Inserts each scraped product with site, timestamp, and method metadata.
- Stores name, price, price_float, price_inr, link, specs.
- Exposes `close()` for graceful shutdown.

### `config.py` -- the configuration

What it does:

- Defines `SITES_CONFIG` (all supported sites, selectors, regex, currency).
- Sets retry counts, timeouts, delays, proxy settings.
- Defines Gemini settings: `GEMINI_API_KEY`, `GEMINI_MODEL`, `LLM_HTML_MAX_CHARS`.
- Sets email alert and scheduler configuration.

### `alerts.py` -- the notifier

What it does:

- Connects to an SMTP server (default Gmail).
- Sends a formatted email with site name, timestamp, error message, and retry count.
- Only active when `EMAIL_CONFIG.enabled = True` in `config.py`.

### `scheduler.py` -- the automation

What it does:

- Uses the `schedule` library to trigger `main.py` at `SCHEDULE_TIME` daily.
- Runs in an infinite loop checking every minute.
- Supports `run_now()` for immediate testing.

---

## Important Limitations

### Sites that WILL work

- `books.toscrape.com` (practice site, no anti-bot)
- `robu.in` (simple Indian e-commerce)
- Any site with JSON-LD structured data
- Most static HTML sites without Cloudflare / Akamai protection

### Sites that MIGHT work

- Sites with moderate anti-bot (VijaySales, Meesho with delays)
- Sites that allow Playwright browser automation

### Sites that WILL NOT work

- `amazon.in` and `flipkart.com` -- aggressive bot detection with CAPTCHA and fingerprinting
- Pure JavaScript-rendered SPAs that return empty HTML to scrapers
- Sites using image-based prices (canvas rendering)
- Sites with API-only content (no HTML to scrape)

> **For Amazon, Flipkart, and similar sites**, the LLM (Gemini) fallback is your best shot. It can read the rendered page through the HTML even when traditional selectors fail. See the [LLM Fallback section](#llm-fallback-google-gemini).

### Why these sites block scrapers

Modern e-commerce sites use:

- CAPTCHA challenges (visual and behavioral)
- IP reputation checks (blocking datacenter IPs)
- Browser fingerprinting (canvas, WebGL, fonts, plugins)
- Behavioral analysis (mouse movement, scroll patterns)
- Network timing analysis
- Device sensor data (mobile)

---

## Roadmap

- [x] JSON-LD auto-detection
- [x] CSS selector extraction
- [x] Regex fallback
- [x] Fuzzy self-healing
- [x] LLM (Google Gemini) fallback with opt-in prompt
- [x] Source designation in terminal, logs, and CSV
- [x] Smart MRP vs selling price detection
- [x] Price recovery from raw HTML
- [ ] Streamlit live dashboard
- [ ] Visual diff tool (before / after redesign)
- [ ] Slack and Discord webhook alerts
- [ ] Confidence scoring per product
- [ ] Docker containerization
- [ ] PyPI package release

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| HTML parsing | BeautifulSoup4 with `lxml` backend |
| HTTP requests | `requests` with retry logic |
| Browser automation | Playwright (Chromium) |
| LLM | Google Gemini (`gemini-2.0-flash`) via `google-generativeai` |
| Database | SQLite3 (built-in) |
| Scheduling | `schedule` library |
| Logging | Python `logging` module |

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- BeautifulSoup4 for robust HTML parsing
- Playwright team for browser automation
- Google for the free Gemini API
- The open-source community for inspiration
