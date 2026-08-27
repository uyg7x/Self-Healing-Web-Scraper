import sqlite3
import logging
from pathlib import Path
from typing import List, Dict, Optional
from config import DB_PATH

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.db_path = Path(DB_PATH)
        self.conn = None
        self._connect()
        self._create_tables()
    
    def _connect(self):
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
    
    def _create_tables(self):
        cursor = self.conn.cursor()
        # Removed image columns!
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                site_name TEXT NOT NULL,
                product_name TEXT NOT NULL,
                price_text TEXT,
                price_float REAL,
                price_inr TEXT,
                product_link TEXT,
                image_url TEXT,
                specs TEXT,
                scrape_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                scrape_method TEXT,
                selector_index INTEGER,
                self_healed INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()

        # ------------------------------------------------------------------
        # Migration: add image_url column to pre-existing tables that lack it
        # ------------------------------------------------------------------
        cursor.execute("PRAGMA table_info(products)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        if "image_url" not in existing_cols:
            cursor.execute("ALTER TABLE products ADD COLUMN image_url TEXT")
            self.conn.commit()
            logger.info("Migrated: added image_url column to products table")
    
    def save_products(self, products: List[Dict], site_name: str, scrape_info: Dict):
        if not products: return
        cursor = self.conn.cursor()
        for product in products:
            try:
                cursor.execute("""
                    INSERT INTO products (site_name, product_name, price_text, price_float, price_inr, product_link, image_url, specs, scrape_method, selector_index, self_healed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    site_name, product.get("name", ""), product.get("price", ""),
                    product.get("price_float"), product.get("price_inr"),
                    product.get("link"), product.get("image_url"), product.get("specs"),
                    scrape_info.get("method", "unknown"),
                    scrape_info.get("strategy_index", -1),
                    1 if product.get("healed") else 0,
                ))
            except sqlite3.Error as e:
                logger.error(f"Database insert error: {e}")
        self.conn.commit()
        logger.info(f"Saved {len(products)} products to database")
    
    def close(self):
        if self.conn: self.conn.close()