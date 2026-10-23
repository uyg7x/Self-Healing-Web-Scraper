import asyncio
import os
import subprocess
import time

from playwright.async_api import async_playwright


async def main():
    # 1. Launch real Chrome with Remote Debugging enabled
    chrome_path = (
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"  # Update if needed
    )
    user_data_dir = os.path.abspath("data/chrome_profile")

    print("Launching Chrome... Please log into Amazon in the window that opens.")
    subprocess.Popen(
        [
            chrome_path,
            "--remote-debugging-port=9222",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
        ]
    )

    # Give you 20 seconds to log in or solve CAPTCHA
    print("Waiting 20 seconds for you to log in...")
    time.sleep(20)

    print("Attaching Playwright to the open browser...")
    async with async_playwright() as p:
        # Connect to the open Chrome browser via CDP
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")

        # Get the existing context (your logged-in session)
        context = browser.contexts[0]
        page = await context.new_page()

        print("Navigating to Amazon...")
        await page.goto(
            "https://www.amazon.in/s?k=Laptop+Asus+Tuf+A15",
            wait_until="domcontentloaded",
        )

        # Wait for page to load
        await page.wait_for_timeout(3000)

        html = await page.content()
        print(f"Successfully grabbed {len(html)} characters of HTML from Amazon!")

        # Save the HTML so you can inspect it
        with open("amazon_debug.html", "w", encoding="utf-8") as f:
            f.write(html)

        print("Saved HTML to amazon_debug.html. You can now parse this file.")

        # We keep the browser open so you can see it
        input("Press Enter to close the browser...")


if __name__ == "__main__":
    asyncio.run(main())
