import random
import time


class ProxyManager:
   

    def __init__(self, proxy_list: list = None):
        self.proxies = proxy_list or []
        self.banned_proxies = {}

    def get(self) -> str:
        if not self.proxies:
            return None

        now = time.time()
        
        self.banned_proxies = {p: t for p, t in self.banned_proxies.items() if t > now}

        
        available = [p for p in self.proxies if p not in self.banned_proxies]

        if not available:
            print("[!] All proxies are currently benched. Using DIRECT connection.")
            return None

        return random.choice(available)

    def mark_failed(self, proxy_url: str):
        if proxy_url:
           
            self.banned_proxies[proxy_url] = time.time() + 300
            print(f"  [-] Benched proxy for 5 mins: {proxy_url}")

    def mark_ok(self, proxy_url: str):
        pass
