
```markdown
# Contributing to Tea Scraper

First off, thank you for considering contributing! 🎉 This project aims to build a resilient, anti-bot price intelligence engine, and community contributions are what make it better. 

Whether you're fixing a broken CSS selector, adding a new site parser, or improving the delay algorithms, your help is appreciated.

##  Setting Up Your Development Environment

To ensure a smooth contribution process, please follow these detailed steps. This setup isolates the project dependencies and ensures your changes don’t interfere with your system’s global Python installation.

### 1. Fork and Clone the Repository
Working on a fork ensures the main repository stays clean and allows you to test your changes safely.

1. Go to the [Self-Healing-Web-Scraper repository](https://github.com/uyg7x/Tea_Scraper).
2. Click the **Fork** button in the top-right corner to create a copy under your own GitHub account.
3. Clone **your forked** repository to your local machine:

```bash
# Replace YOUR-USERNAME with your actual GitHub username
git clone https://github.com/uyg7x/Tea_Scraper.git
cd Tea_Scraper
# Add the original repository as an "upstream" remote to easily sync future updates
git remote add upstream https://github.com/uyg7x/Tea_Scraper.git
```

### 2. Set Up a Python Virtual Environment
**Highly Recommended:** A virtual environment keeps project dependencies isolated. Choose the commands below based on your operating system:

**For macOS & Linux:**
```bash
python3 -m venv .venv312
source .venv312/bin/activate
```

**For Windows (PowerShell):**
```powershell
python -m venv .venv312
# Note: If you get an execution policy error, run: Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
.\.venv312\Scripts\Activate.ps1
```
*Pro Tip: You will know the virtual environment is active because you will see `(.venv312)` at the beginning of your terminal prompt.*

### 3. Install Project Dependencies
Once your virtual environment is activated, install all required Python packages:

```bash
# Upgrade pip to the latest version
python -m pip install --upgrade pip

# Install all Python dependencies listed in requirements.txt
pip install -r requirements.txt
```

### 4. Install the Stealth Browser (Camoufox)
Unlike standard Playwright scrapers, this project uses **Camoufox**, a heavily modified Firefox fork, for deep stealth. You must download its binary engine:

```bash
python -m camoufox fetch
```
*(Note: This downloads a ~1.3GB binary. You only need to do this once).*

### 5. Configure Environment Variables (Optional)
The scraper uses optional LLM fallbacks (Gemini/Qwen) when all CSS/Regex extraction fails. If you want to test these features:
1. Get a free API key from [Google AI Studio](https://aistudio.google.com/).
2. In the root directory, copy `.env.example` to a new file named `.env`.
3. Add your key:
```env
GEMINI_API_KEY=AIzaSy...your_actual_api_key_here...
```

> **⚠️ Security Reminder:** The `.env` file is already in `.gitignore`. **Never** commit your `.env` file or share your API keys publicly.

---

## 🚀 Warming Up Profiles (Crucial Step)

This scraper does not use fresh browsers for every request, as that triggers instant CAPTCHAs. Instead, it uses **persistent browser profiles**. 

Before you can scrape Amazon, eBay, Newegg, etc., you must "warm up" their profiles by logging in manually once.

```bash
python tools/warm_site.py all
```
* A Camoufox browser will open for each site.
* Log in normally (if required), solve any CAPTCHAs, and browse for 30 seconds.
* Press `Enter` in your terminal to save the profile and move to the next site.

---

## ✅ Verify Your Setup (Smoke Test)

Before you start coding, let’s make sure everything is wired up correctly. Run the scraper:

```bash
python main.py
```
1. Enter a product (e.g., `motherboard`).
2. Set max pages to `2`.
3. Select the sites you just warmed up.
4. Choose `4` for "No AI" to test the heuristic cascade.

If it successfully saves a CSV file in the `data/` folder, you are ready to code!

---

##  Where to Contribute?

If you want to help but aren't sure where to start, here are the most impactful areas:

1. **Add New Sites:** Add new e-commerce targets to `config.py`. We are always looking for more global sites (e.g., Walmart, Target, AliExpress).
2. **Fix Broken Selectors:** E-commerce sites change their layout constantly. If a site returns 0 products, update its CSS selectors in `config.py`.
3. **Improve the Anti-Bot Layer:** If you know better delay algorithms or browser fingerprint spoofing techniques, tweak `antiban_engine.py` or `human_delay.py`.
4. **Dashboard UI:** The C-based dashboard (`dashboard.c`) or the Streamlit dashboard (`dashboard.py`) can always use more charts, filters, or UI polish.

## 📝 Pull Request Guidelines
* **Keep it focused:** 1 PR = 1 feature or bug fix.
* **Test your code:** Run `python main.py` before submitting to ensure you didn't break the extraction cascade.
* **Update Docs:** If you add a new site or feature, update the `README.md` or this file.

Thank you for helping make this the most resilient scraper on GitHub! 🚀
```
