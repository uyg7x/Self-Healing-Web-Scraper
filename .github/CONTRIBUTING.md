Contributing to Tea Scraper
Thank you for your interest in contributing! 🎉 This project aims to build a resilient, AI-powered web scraper, and community contributions make it better.

Setting Up Your Development Environment
To ensure a smooth contribution process, please follow these detailed steps to set up your local development environment. This setup isolates the project dependencies and ensures your changes don’t interfere with your system’s global Python installation.

1. Fork and Clone the Repository
Working on a fork ensures the main repository stays clean and allows you to test your changes safely.

Go to the Self-Healing-Web-Scraper repository.

Click the Fork button in the top-right corner to create a copy under your own GitHub account.

Clone your forked repository to your local machine:

# Replace YOUR-USERNAME with your actual GitHub username
git clone https://github.com/YOUR-USERNAME/Self-Healing-Web-Scraper.git

# Navigate into the project directory
cd Self-Healing-Web-Scraper

# Add the original repository as an "upstream" remote to easily sync future updates
git remote add upstream https://github.com/uyg7x/Self-Healing-Web-Scraper.git


2. Set Up a Python Virtual Environment
Highly Recommended: A virtual environment keeps project dependencies isolated. Choose the commands below based on your operating system: For macOS & Linux:

Create the virtual environment named 'venv'
python3 -m venv venv

Activate the virtual environment
source venv/bin/activate

For Windows (Command Prompt):

:: Create the virtual environment python -m venv venv

:: Activate the virtual environment venv\Scripts\activate.bat

For Windows (PowerShell):

Create the virtual environment
python -m venv venv

Activate the virtual environment
(Note: If you get an execution policy error, run: Set-ExecutionPolicy RemoteSigned -Scope CurrentUser)
venv\Scripts\Activate.ps1

Pro Tip: You will know the virtual environment is active because you will see (venv) at the beginning of your terminal prompt.

Install Project Dependencies
Once your virtual environment is activated, install all required Python packages and browser binaries.# Upgrade pip to the latest version to avoid installation warnings python -m pip install --upgrade pip

Install all Python dependencies listed in requirements.txt
pip install -r requirements.txt

Install the Stealth Browser (Camoufox)
Because this project relies on advanced fingerprint spoofing to bypass CAPTCHAs, we use Camoufox instead of standard Playwright. You must download the browser engine:

python -m camoufox fetch
(Note: This downloads a ~1.3GB binary. You only need to do this once).

Configure Environment Variables The scraper uses an optional LLM fallback strategy powered by Google Gemini or Qwen. To test this feature, you need an API key.

Get a free API key from Google AI Studio(https://aistudio.google.com/) . In the root directory of the project, create a new file named exactly .env (note the leading dot). Open the .env file in any text editor and add your key like this: GEMINI_API_KEY=AIzaSy...your_actual_api_key_here...

Security Reminder: The .env file is already listed in .gitignore. Never commit your .env file to GitHub or share your API key publicly.

Warming Up Profiles (Crucial Step)
This scraper does not use fresh browsers for every request, as that triggers instant CAPTCHAs. Instead, it uses persistent browser profiles.

Before you can scrape Amazon, eBay, Newegg, etc., you must "warm up" their profiles by logging in manually once:

python tools/warm_site.py all
A Camoufox browser will open for each site.
Log in normally (if required), solve any CAPTCHAs, and browse for 30 seconds.
Press Enter in your terminal to save the profile and move to the next site.

Verify Your Setup (Smoke Test) Before you start coding, let’s make sure everything is wired up correctly. Run the scraper:

python main.py
Enter a product (e.g., motherboard).
Set max pages to 2.
Select the sites you just warmed up.
Choose 4 for "No AI" to test the heuristic cascade.

If it successfully saves a CSV file in the data/ folder, you are ready to code!

Where to Contribute?
If you want to help but aren't sure where to start, here are the most impactful areas:

Add New Sites: Add new e-commerce targets to config.py. We are always looking for more global sites (e.g., Walmart, Target, AliExpress).
Fix Broken Selectors: E-commerce sites change their layout constantly. If a site returns 0 products, update its CSS selectors in config.py.
Improve the Anti-Bot Layer: If you know better delay algorithms or browser fingerprint spoofing techniques, tweak antiban_engine.py or human_delay.py.
Dashboard UI: The C-based dashboard (dashboard.c) or the Streamlit dashboard (dashboard.py) can always use more charts, filters, or UI polish.

Pull Request Guidelines
Keep it focused: 1 PR = 1 feature or bug fix.
Test your code: Run python main.py before submitting to ensure you didn't break the extraction cascade.
Update Docs: If you add a new site or feature, update the README.md or this file.

Thank you for helping make this the most resilient scraper on GitHub! 🚀
