import logging
import sqlite3
from pathlib import Path

from .config import DB_PATH
from utils.url_utils import content_fingerprint

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
        c = self.conn.cursor()
        c.execute("""
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
                content_fingerprint TEXT,
                page_number INTEGER,
                engine_used TEXT,
                scrape_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                scrape_method TEXT,
                selector_index INTEGER,
                self_healed INTEGER DEFAULT 0
            )
        """)
        self.conn.commit()


        c.execute("PRAGMA table_info(products)")
        existing = {row[1] for row in c.fetchall()}
        for col, decl in [
            ("image_url", "TEXT"),
            ("content_fingerprint", "TEXT"),
            ("page_number", "INTEGER"),
            ("engine_used", "TEXT"),
        ]:
            if col not in existing:
                c.execute(f"ALTER TABLE products ADD COLUMN {col} {decl}")
                logger.info(f"Migrated: added {col} to products")
        self.conn.commit()

        c.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_products_dedupe
            ON products (site_name, content_fingerprint)
        """)
        self.conn.commit()

    def save_products(self, products: list[dict], site_name: str, scrape_info: dict):
        if not products:
            return

        c = self.conn.cursor()
        inserted = 0

        for p in products:
            fp = p.get("content_fingerprint") or content_fingerprint(p)
            try:
                c.execute(
                    """
                    INSERT OR IGNORE INTO products
                    (site_name, product_name, price_text, price_float, price_inr,
                     product_link, image_url, specs, content_fingerprint,
                     page_number, engine_used, scrape_method, selector_index, self_healed)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        site_name,
                        p.get("name", ""),
                        p.get("price", ""),
                        p.get("price_float"),
                        p.get("price_inr"),
                        p.get("link"),
                        p.get("image_url"),
                        p.get("specs"),
                        fp,
                        p.get("page_number"),
                        p.get("engine_used"),
                        scrape_info.get("method", "unknown"),
                        scrape_info.get("strategy_index", -1),
                        1 if p.get("healed") else 0,
                    ),
                )
                if c.rowcount > 0:
                    inserted += 1
            except sqlite3.Error as e:
                logger.error(f"DB insert error: {e}")

        self.conn.commit()
        logger.info(f"Saved {inserted}/{len(products)} new products for {site_name}")

    def close(self):
        if self.conn:
            self.conn.close()
