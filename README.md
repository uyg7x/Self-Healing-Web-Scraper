# Self-Healing Scraper

### A high-resilience web scraping framework that automatically adapts to website redesigns using a multi-stage fallback chain and LLM-powered recovery.

Traditional web scrapers are "brittle"—a single change in a website's CSS class or HTML structure can break the entire pipeline. This project solves that problem by implementing a **self-healing architecture**. Instead of relying on a single selector, it employs five increasingly flexible strategies to ensure data continuity even after a total site redesign.

<br>

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-success)
![Maintenance](https://img.shields.io/badge/Maintained-Yes-brightgreen)

<br>

[Quick Start](#quick-start) &nbsp;&bull;&nbsp; [Demo](#demo) &nbsp;&bull;&nbsp; [Features](#features) &nbsp;&bull;&nbsp; [Architecture](#architecture) &nbsp;&bull;&nbsp; [Technical Deep-Dive](#technical-deep-dive) &nbsp;&bull;&nbsp; [File Documentation](#file-documentation) &nbsp;&bull;&nbsp; [Roadmap](#roadmap)

---

<div align="center">

## Demo

</div>

### Screenshots

> Drop your screenshot files into `docs/screenshots/` using these exact filenames, then the images will show up here automatically.

<br>

**Terminal run showing all 5 strategies and the LLM opt-in prompt:**

<p align="center">
  <img src="docs/screenshots/terminal-run.png" alt="Terminal run showing all 5 strategies" width="900"/>
  <br/>
  <sub><i>Replace this image by saving your screenshot as <code>docs/screenshots/terminal-run.png</code></i></sub>
</p>

<br>

**Generated CSV with the Source designation column:**

<p align="center">
  <img src="docs/screenshots/csv-output.png" alt="CSV output with Source column" width="900"/>
  <br/>
  <sub><i>Replace this image by saving your screenshot as <code>docs/screenshots/csv-output.png</code></i></sub>
</p>

<br>

**Architecture / strategy flow diagram:**

<p align="center">
  <img src="docs/screenshots/architecture.png" alt="Architecture diagram" width="900"/>
  <br/>
  <sub><i>Replace this image by saving your diagram as <code>docs/screenshots/architecture.png</code></i></sub>
</p>

<br>

### Video walkthrough

> Add your YouTube link below. Replace `YOUR_VIDEO_ID` with the 11-character ID from the YouTube URL (the part after `v=`).

<br>

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
| **JSON-LD Auto-Detection** | Parses `<script type="application/ld+json">` blocks; survives most redesigns. |
| **CSS Selector Extraction** | Tries each configured selector in priority order. |
| **Regex Fallback** | Pattern-matches raw HTML when CSS is broken. |
| **Fuzzy Self-Healing** | Finds price symbols, scores nearby text blocks, builds product guesses. |
| **LLM (Gemini) Fallback** | Asks Google Gemini to read messy HTML when all four traditional methods fail. |
| **Source Designation** | Every result is tagged with `Website - Strategy` in the terminal, logs, and CSV. |
| **Opt-in AI Mode** | Gemini is only called when you answer `y` to a per-site prompt. |
| **Dual Fetching** | `requests` for fast static pages, Playwright for JavaScript-rendered ones. |
| **Smart Price Recovery** | Distinguishes MRP from selling price; recovers missing prices from raw HTML. |
| **Multi-Currency** | Auto-converts USD, GBP, and EUR into Indian Rupees. |
| **Data Validation** | Rejects junk rows, scrapes, and bot-detection blocks. |
| **SQLite History** | Stores every result with timestamp and extraction method. |
| **Self-Learning** | Promotes selectors and strategies that historically succeed. |
| **CSV Export** | Per-search timestamped comparison file in `data/`. |
| **Daily Scheduler** | Optional `scheduler.py` to run automatically at 09:00. |
| **Email Alerts** | Optional failure notifications via SMTP. |

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

## Technical Deep-Dive

### The Extraction Pipeline

The scraper employs a **cascading fallback mechanism**. If a high-precision strategy fails, it automatically drops to a more flexible, lower-precision strategy.

1. **JSON-LD (Structured Data)**
   - **Logic**: Parses Schema.org metadata embedded in the HTML.
   - **Resilience**: Extremely high. Metadata is rarely changed during visual redesigns.

2. **CSS Selectors**
   - **Logic**: Targets specific HTML elements via classes/IDs.
   - **Resilience**: Medium. Fast, but breaks if the developer renames a class.

3. **Regex Fallback**
   - **Logic**: Uses regular expressions to find patterns (e.g., `₹[\d,]+`).
   - **Resilience**: High. Works as long as the text pattern remains consistent.

4. **Fuzzy Self-Healing**
   - **Logic**: Heuristic-based search. It finds price symbols and then scores nearby text blocks based on length, capitalization, and product-related keywords.
   - **Resilience**: Very High. Works even when the entire HTML structure is rewritten.

5. **LLM Fallback (Google Gemini)**
   - **Logic**: Sends a cleaned version of the HTML to `gemini-2.0-flash` with a strict JSON prompt.
   - **Resilience**: Absolute. The LLM "reads" the page like a human would.

### Source Designation & Traceability

To ensure data integrity, every product is tagged with its **Source**. This allows the user to audit the quality of the data.
- **Example**: `Amazon India - CSS selector` vs `Amazon India - Gemini AI (LLM)`.

### Price Recovery Logic

To avoid scraping the **MRP (Maximum Retail Price)** instead of the **Selling Price**, the engine implements a window-scan:
1. Extract a price.
2. Scan the 1500 characters following the product link.
3. Identify all price-like strings.
4. If a lower price is found that isn't marked as "original" or "struck-through," it is selected as the actual selling price.

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- `pip` package manager
- A Google Gemini API key (optional, for LLM fallback)

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

---

## Configuration

### Adding a New Site

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

### LLM Fallback Setup

The code reads the API key from the environment variable `GEMINI_API_KEY`.

**Windows PowerShell:**
```powershell
$env:GEMINI_API_KEY = "AIzaSy...your_key_here"
```

**Linux / macOS:**
```bash
export GEMINI_API_KEY="AIzaSy...your_key_here"
```

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
|-- .env.example           Template for local secrets
|-- docs/
|   |-- screenshots/       Demo images
|-- data/                  Output folder (gitignored)
```

---

## File Documentation

### `main.py`
Orchestrates the search process, handles user interaction, and generates the final CSV output with source designations.

### `scraper_engine.py`
The core engine implementing the 5-stage fallback pipeline and the smart price recovery logic.

### `llm_healer.py`
Handles HTML trimming and communication with the Google Gemini API to extract products from unstructured HTML.

### `self_healing.py`
The memory system that tracks successful strategies and promotes them to priority for future runs.

### `validators.py`
Ensures data quality by filtering out "garbage" rows (menu items, ads, etc.).

### `database.py`
Manages persistent storage of all scraped products in a local SQLite database.

### `config.py`
Centralized configuration for all supported websites, currency rates, and API settings.

---

## Important Limitations

- **Anti-Bot Systems**: Sites like Amazon and Flipkart use aggressive fingerprinting. The LLM fallback is the most effective way to bypass these, but success is not guaranteed.
- **Dynamic Content**: Pure SPAs (Single Page Applications) may require Playwright to be enabled in `config.py`.

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
| LLM | Google Gemini (`gemini-2.0-flash`) |
| Database | SQLite3 |
| Scheduling | `schedule` library |

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
