import asyncio

from session_manager import WarmSessionManager

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"


async def main():
    print(f"\n{CYAN}{'=' * 60}{RESET}")
    print(f"{YELLOW}AMAZON WARM-UP TOOL{RESET}")
    print(f"{CYAN}{'=' * 60}{RESET}")
    print("Amazon blocks standard scrapers. To bypass this, we")
    print("need to save your real browser cookies.\n")
    print("A browser window will open. Please log into Amazon normally.")
    print("Once you are fully logged in and see the homepage, come")
    print("back to this terminal and press Enter.\n")

    mgr = WarmSessionManager("amazon")
    try:
        success = await mgr.warm_up("https://www.amazon.in/", headless=False)
        if success:
            print(
                f"\n{GREEN}✓ Success! Cookies saved to data/sessions/amazon_cookies.json{RESET}"
            )
            print(
                f"{GREEN}You can now run `python main.py` and it will bypass Amazon's blocks.{RESET}\n"
            )
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCancelled.")
