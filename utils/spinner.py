import asyncio
import sys

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"

FRAMES = ["⣾", "⣽", "⣻", "⢿", "⡿", "⣟", "⣯", "⣷"]
SIMPLE = ["|", "/", "-", "\\"]


async def _spin_loop(message: str, stop_event: asyncio.Event, color: str, frames):
    i = 0
    pad_len = len(message) + 8
    while not stop_event.is_set():
        frame = frames[i % len(frames)]
        sys.stdout.write(f"\r{color}{frame}{RESET} {message}")
        sys.stdout.flush()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=0.1)
        except asyncio.TimeoutError:
            pass
        i += 1
    sys.stdout.write("\r" + " " * pad_len + "\r")
    sys.stdout.flush()


class Spinner:
   

    def __init__(self, message: str, color: str = CYAN, frames=None):
        self.message = message
        self.color = color
        self.frames = frames or FRAMES
        self.stop_event = None
        self.task = None

    async def __aenter__(self):
        self.stop_event = asyncio.Event()
        self.task = asyncio.create_task(
            _spin_loop(self.message, self.stop_event, self.color, self.frames)
        )
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.stop_event:
            self.stop_event.set()
        if self.task:
            try:
                await self.task
            except Exception:
                pass
        return False

    def finish(self, final_text: str, ok: bool = True):
        if self.stop_event:
            self.stop_event.set()
        mark = f"{GREEN}✓{RESET}" if ok else f"{RED}✗{RESET}"
        print(f"{mark} {final_text}")


async def spin_fetch(site_name: str, page_num: int, engine_hint: str = "fast"):
    return Spinner(
        f"{BOLD}{site_name}{RESET} p{page_num} — fetching ({engine_hint})...",
        color=CYAN,
    )


async def spin_render(site_name: str, page_num: int):
    return Spinner(
        f"{BOLD}{site_name}{RESET} p{page_num} — rendering in browser...",
        color=MAGENTA,
    )


async def spin_extract(site_name: str, page_num: int):
    return Spinner(
        f"{BOLD}{site_name}{RESET} p{page_num} — extracting products...",
        color=YELLOW,
    )


async def spin_validate(site_name: str, count: int):
    return Spinner(
        f"{BOLD}{site_name}{RESET} — scoring & validating {count} items...",
        color=CYAN,
    )
