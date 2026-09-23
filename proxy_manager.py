from datetime import datetime, timedelta
import random
import time
from typing import Optional

class ProxyManager:
    def __init__(self, proxies: list):
        self.proxies = proxies
        self.ban_list = {}  # proxy -> unban time

    def get(self) -> Optional[str]:
        """
        Returns an available proxy. If none are available, returns None 
        to allow a direct connection instead of hanging.
        """
        now = datetime.now()
        
        # Clean up expired bans
        self.ban_list = {
            proxy: expiry for proxy, expiry in self.ban_list.items() 
            if expiry > now
        }
        
        # Find available proxies
        available = [p for p in self.proxies if p not in self.ban_list]
        
        if not available:
            print("[!] No proxies available. Proceeding with DIRECT connection (no proxy).")
            return None
            
        selected_proxy = random.choice(available)
        print(f"[+] Using proxy: {selected_proxy}")
        return selected_proxy

    def ban(self, proxy: str):
        """Blacklist proxy for 24 hours"""
        self.ban_list[proxy] = datetime.now() + timedelta(hours=24)
        print(f"[-] Banned proxy for 24h: {proxy}")