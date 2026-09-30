"""
scraper_manager/energy.py

Scrapes exchange rates, ministry-of-electricity news, and fuel prices,
then upserts them into PostgreSQL.
"""

import json
import re
from datetime import datetime

import psycopg2
import requests
from bs4 import BeautifulSoup
from psycopg2.extras import execute_batch

from .base import db_config, get_connection, get_logger, with_retry

log = get_logger(__name__)

# Keep DB_CONFIG as a property so existing callers (scheduler.py) still work.
DB_CONFIG = db_config()


# ── schema ─────────────────────────────────────────────────────────────────────

def initialize_postgresql_db(config: dict | None = None):
    """Creates PostgreSQL tables with PRIMARY KEY constraints for UPSERT ops."""
    conn = psycopg2.connect(**(config or db_config()))
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            currency_code VARCHAR(10) PRIMARY KEY,
            rate_syp      NUMERIC(12, 2) NOT NULL,
            source        VARCHAR(100) DEFAULT 'cb.gov.sy',
            last_updated  TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_articles (
            source_url   TEXT PRIMARY KEY,
            source_name  VARCHAR(100) NOT NULL,
            title        TEXT NOT NULL,
            category     VARCHAR(100),
            last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fuel_prices (
            fuel_type    VARCHAR(100) PRIMARY KEY,
            price_syp    NUMERIC(12, 2) NOT NULL,
            unit         VARCHAR(50) DEFAULT 'SYP per unit',
            last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    return conn


# ── scrapers ───────────────────────────────────────────────────────────────────

@with_retry(max_attempts=3, delay=2.0)
def scrape_central_bank_live() -> tuple[dict, list]:
    """Extracts foreign exchange rates and news from cb.gov.sy."""
    url = "https://cb.gov.sy/index.php?lang=2"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }

    rates: dict = {}
    news: list = []

    response = requests.get(url, headers=headers, timeout=12)
    if response.status_code != 200:
        log.warning("central_bank: unexpected status %d", response.status_code)
        return rates, news

    soup = BeautifulSoup(response.text, "html.parser")
    text_content = soup.get_text()

    currency_patterns = {
        "USD": r"(?:USD|الدولار الأمريكي)\s*([\d\.]+)",
        "EUR": r"(?:EUR|يورو)\s*([\d\.]+)",
        "GBP": r"(?:GBP|جنيه استرليني)\s*([\d\.]+)",
        "SAR": r"(?:SAR|الريال السعودي)\s*([\d\.]+)",
        "AED": r"(?:AED|الدرهم الإماراتي)\s*([\d\.]+)",
        "JOD": r"(?:JOD|الدينار الأردني)\s*([\d\.]+)",
        "KWD": r"(?:KWD|الدينار الكويتي)\s*([\d\.]+)",
    }

    for code, pattern in currency_patterns.items():
        match = re.search(pattern, text_content)
        if match:
            rates[code] = float(match.group(1))

    news_elements = soup.find_all(
        ["a", "h3", "h4"], text=re.compile(r"[\u0600-\u06FF]+")
    )
    for elem in news_elements:
        title = elem.get_text(strip=True)
        href = elem.get("href", f"cb.gov.sy/news/{hash(title)}")
        if not href.startswith("http"):
            href = f"https://cb.gov.sy/{href.lstrip('/')}"

        if len(title) > 20 and "مصرف" in title:
            news.append(
                {
                    "source_url": href,
                    "source_name": "Central Bank of Syria",
                    "title": title,
                    "category": "Monetary Policy",
                }
            )
        if len(news) >= 3:
            break

    log.info("central_bank: %d rates, %d news items", len(rates), len(news))
    return rates, news


@with_retry(max_attempts=3, delay=2.0)
def scrape_ministry_electricity_live() -> list:
    """Extracts press releases from moe.gov.sy."""
    url = "http://moe.gov.sy/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }

    news_data: list = []

    response = requests.get(url, headers=headers, timeout=12)
    if response.status_code != 200:
        log.warning("ministry_electricity: unexpected status %d", response.status_code)
        return news_data

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.find_all(
        ["div", "article", "a"],
        class_=re.compile(r"news|item|post|card|title", re.I),
    )

    for card in cards:
        text = card.get_text(strip=True)
        link = card.get("href") if card.name == "a" else None
        if not link:
            a_tag = card.find("a")
            link = a_tag.get("href") if a_tag else None

        source_url = link or f"http://moe.gov.sy/news/{hash(text[:30])}"
        if not source_url.startswith("http"):
            source_url = f"http://moe.gov.sy/{source_url.lstrip('/')}"

        if len(text) > 25:
            news_data.append(
                {
                    "source_url": source_url,
                    "source_name": "Ministry of Electricity",
                    "title": text[:150],
                    "category": "Electricity Infrastructure",
                }
            )
        if len(news_data) >= 5:
            break

    log.info("ministry_electricity: %d news items", len(news_data))
    return news_data


@with_retry(max_attempts=3, delay=2.0)
def scrape_live_fuel_rates() -> dict:
    """Scrapes live fuel prices from sypnow.com."""
    url = "https://sypnow.com/en/fuel"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }

    fuel_data: dict = {}

    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        log.warning("fuel_rates: unexpected status %d", response.status_code)
        return fuel_data

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text()

    patterns = {
        "Gasoline 95 Octane": r"95-octane[^\d]*([\d\.]+)",
        "Gasoline 90 Octane": r"90-octane[^\d]*([\d\.]+)",
        "Diesel":             r"diesel[^\d]*([\d\.]+)",
        "LPG Gas Cylinder":   r"gas cylinder[^\d]*([\d\.]+)",
    }
    for label, pattern in patterns.items():
        m = re.search(pattern, text, re.I)
        if m:
            fuel_data[label] = float(m.group(1))

    log.info("fuel_rates: %d types scraped", len(fuel_data))
    return fuel_data


# ── persistence ────────────────────────────────────────────────────────────────

def upsert_to_postgres(conn, cbs_rates: dict, news_items: list, fuel_rates: dict) -> None:
    """Performs atomic UPSERTs for all three data types."""
    cursor = conn.cursor()
    now = datetime.utcnow()

    # Exchange rates
    rate_records = [
        (code, rate, "cb.gov.sy", now) for code, rate in cbs_rates.items()
    ]
    execute_batch(
        cursor,
        """
        INSERT INTO exchange_rates (currency_code, rate_syp, source, last_updated)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (currency_code) DO UPDATE SET
            rate_syp     = EXCLUDED.rate_syp,
            source       = EXCLUDED.source,
            last_updated = EXCLUDED.last_updated;
        """,
        rate_records,
    )

    # News articles
    news_records = [
        (
            item["source_url"],
            item["source_name"],
            item["title"],
            item.get("category", "General"),
            now,
        )
        for item in news_items
    ]
    execute_batch(
        cursor,
        """
        INSERT INTO news_articles (source_url, source_name, title, category, last_updated)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source_url) DO UPDATE SET
            title        = EXCLUDED.title,
            category     = EXCLUDED.category,
            last_updated = EXCLUDED.last_updated;
        """,
        news_records,
    )

    # Fuel prices
    fuel_records = [
        (
            fuel_type,
            price,
            "SYP per cylinder" if "Cylinder" in fuel_type else "SYP per liter",
            now,
        )
        for fuel_type, price in fuel_rates.items()
    ]
    execute_batch(
        cursor,
        """
        INSERT INTO fuel_prices (fuel_type, price_syp, unit, last_updated)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (fuel_type) DO UPDATE SET
            price_syp    = EXCLUDED.price_syp,
            unit         = EXCLUDED.unit,
            last_updated = EXCLUDED.last_updated;
        """,
        fuel_records,
    )

    conn.commit()
    log.info(
        "upsert_to_postgres: %d rates, %d news, %d fuel",
        len(rate_records), len(news_records), len(fuel_records),
    )
