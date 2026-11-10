# Contributing to Self-Healing Web Scraper

Thank you for your interest in contributing! 🎉 This project aims to build a resilient, AI-powered web scraper, and community contributions make it better.

##  Setting Up Your Development Environment

To ensure a smooth contribution process, please follow these detailed steps to set up your local development environment. This setup isolates the project dependencies and ensures your changes don’t interfere with your system’s global Python installation.

### 1. Fork and Clone the Repository
Working on a fork ensures the main repository stays clean and allows you to test your changes safely.

1. Go to the [Self-Healing-Web-Scraper repository](https://github.com/uyg7x/Self-Healing-Web-Scraper).
2. Click the **Fork** button in the top-right corner to create a copy under your own GitHub account.
3. Clone **your forked** repository to your local machine:

   ```bash
   # Replace YOUR-USERNAME with your actual GitHub username
   git clone https://github.com/YOUR-USERNAME/Self-Healing-Web-Scraper.git
   
   # Navigate into the project directory
   cd Self-Healing-Web-Scraper
   
   # Add the original repository as an "upstream" remote to easily sync future updates
   git remote add upstream https://github.com/uyg7x/Self-Healing-Web-Scraper.git


   2. Set Up a Python Virtual Environment
Highly Recommended: A virtual environment keeps project dependencies isolated. Choose the commands below based on your operating system:
For macOS & Linux:

# Create the virtual environment named 'venv'
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate


For Windows (Command Prompt):

:: Create the virtual environment
python -m venv venv

:: Activate the virtual environment
venv\Scripts\activate.bat

For Windows (PowerShell):

# Create the virtual environment
python -m venv venv

# Activate the virtual environment 
# (Note: If you get an execution policy error, run: Set-ExecutionPolicy RemoteSigned -Scope CurrentUser)
venv\Scripts\Activate.ps1


Pro Tip: You will know the virtual environment is active because you will see (venv) at the beginning of your terminal prompt.

3. Install Project Dependencies
   
Once your virtual environment is activated, install all required Python packages and browser binaries.# Upgrade pip to the latest version to avoid installation warnings
python -m pip install --upgrade pip

# Install all Python dependencies listed in requirements.txt
pip install -r requirements.txt

# Install Playwright's Chromium browser binaries (required for the scraper to run)
playwright install chromium

Note: If you are on Linux, Playwright might prompt you to install missing system-level dependencies (like libnss3 or libatk). If so, simply run playwright install-deps when prompted.

4. Configure Environment Variables
The scraper uses an optional LLM fallback strategy powered by Google Gemini. To test this feature, you need an API key.

    Get a free API key from Google AI Studio(https://aistudio.google.com/)
    .
    In the root directory of the project, create a new file named exactly .env (note the leading dot).
    Open the .env file in any text editor and add your key like this:
      GEMINI_API_KEY=AIzaSy...your_actual_api_key_here...

   Security Reminder: The .env file is already listed in .gitignore. Never commit your .env file to GitHub or share your API key publicly.

5. Verify Your Setup (Smoke Test)
Before you start coding, let’s make sure everything is wired up correctly. Run the built-in breakage simulator:
    python main.py --demo
