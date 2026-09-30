import json
import re
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_batch
import requests
from bs4 import BeautifulSoup

# PostgreSQL Connection Configuration
DB_CONFIG = {
    "dbname": "postgres",
    "user": "postgres",
    "password": "Vixingo",
    "host": "localhost",
    "port": "5432",
}


def initialize_postgresql_db(config):
    """Creates PostgreSQL tables with PRIMARY KEY constraints for native UPSERT operations."""
    conn = psycopg2.connect(**config)
    cursor = conn.cursor()

    # 1. Foreign Exchange Rates Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            currency_code VARCHAR(10) PRIMARY KEY,
            rate_syp NUMERIC(12, 2) NOT NULL,
            source VARCHAR(100) DEFAULT 'cb.gov.sy',
            last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 2. News Articles Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS news_articles (
            source_url TEXT PRIMARY KEY,
            source_name VARCHAR(100) NOT NULL,
            title TEXT NOT NULL,
            category VARCHAR(100),
            last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 3. Fuel & Energy Prices Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fuel_prices (
            fuel_type VARCHAR(100) PRIMARY KEY,
            price_syp NUMERIC(12, 2) NOT NULL,
            unit VARCHAR(50) DEFAULT 'SYP per unit',
            last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    return conn


def scrape_central_bank_live():
    """Extracts foreign exchange rates and news from cb.gov.sy live."""
    url = "https://cb.gov.sy/index.php?lang=2"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }

    rates = {}
    news = []

    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
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
    except Exception as e:
        print(f"Error scraping Central Bank: {e}")

    return rates, news


def scrape_ministry_electricity_live():
    """Extracts press releases and announcements from moe.gov.sy live."""
    url = "http://moe.gov.sy/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }

    news_data = []

    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code == 200:
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
    except Exception as e:
        print(f"Error scraping Ministry of Electricity: {e}")

    return news_data


def scrape_live_fuel_rates():
    """Scrapes live fuel rates."""
    url = "https://sypnow.com/en/fuel"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }

    fuel_data = {}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            text = soup.get_text()

            octane95 = re.search(r"95-octane[^\d]*([\d\.]+)", text, re.I)
            octane90 = re.search(r"90-octane[^\d]*([\d\.]+)", text, re.I)
            diesel = re.search(r"diesel[^\d]*([\d\.]+)", text, re.I)
            gas_cyl = re.search(r"gas cylinder[^\d]*([\d\.]+)", text, re.I)

            if octane95:
                fuel_data["Gasoline 95 Octane"] = float(octane95.group(1))
            if octane90:
                fuel_data["Gasoline 90 Octane"] = float(octane90.group(1))
            if diesel:
                fuel_data["Diesel"] = float(diesel.group(1))
            if gas_cyl:
                fuel_data["LPG Gas Cylinder"] = float(gas_cyl.group(1))
    except Exception as e:
        print(f"Error scraping fuel rates: {e}")

    return fuel_data


def upsert_to_postgres(conn, cbs_rates, news_items, fuel_rates):
    """Performs PostgreSQL atomic UPSERTs using ON CONFLICT (key) DO UPDATE."""
    cursor = conn.cursor()
    now = datetime.utcnow()

    # 1. Upsert Exchange Rates
    rate_records = [
        (code, rate, "cb.gov.sy", now) for code, rate in cbs_rates.items()
    ]
    upsert_rates_query = """
        INSERT INTO exchange_rates (currency_code, rate_syp, source, last_updated)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (currency_code) DO UPDATE SET
            rate_syp = EXCLUDED.rate_syp,
            source = EXCLUDED.source,
            last_updated = EXCLUDED.last_updated;
    """
    execute_batch(cursor, upsert_rates_query, rate_records)

    # 2. Upsert News Articles
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
    upsert_news_query = """
        INSERT INTO news_articles (source_url, source_name, title, category, last_updated)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (source_url) DO UPDATE SET
            title = EXCLUDED.title,
            category = EXCLUDED.category,
            last_updated = EXCLUDED.last_updated;
    """
    execute_batch(cursor, upsert_news_query, news_records)

    # 3. Upsert Fuel Prices
    fuel_records = [
        (
            fuel_type,
            price,
            (
                "SYP per cylinder"
                if "Cylinder" in fuel_type
                else "SYP per liter"
            ),
            now,
        )
        for fuel_type, price in fuel_rates.items()
    ]
    upsert_fuel_query = """
        INSERT INTO fuel_prices (fuel_type, price_syp, unit, last_updated)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (fuel_type) DO UPDATE SET
            price_syp = EXCLUDED.price_syp,
            unit = EXCLUDED.unit,
            last_updated = EXCLUDED.last_updated;
    """
    execute_batch(cursor, upsert_fuel_query, fuel_records)

    conn.commit()


def export_postgres_to_json(conn):
    """Queries PostgreSQL database and prints JSON output of updated records."""
    cursor = conn.cursor()

    # Query Exchange Rates
    cursor.execute("SELECT currency_code, rate_syp, last_updated FROM exchange_rates")
    rates = {
        row[0]: {"rate_syp": float(row[1]), "last_updated": row[2].isoformat()}
        for row in cursor.fetchall()
    }

    # Query News
    cursor.execute(
        "SELECT source_name, title, category, source_url, last_updated FROM news_articles"
    )
    news = [
        {
            "source": row[0],
            "title": row[1],
            "category": row[2],
            "url": row[3],
            "last_updated": row[4].isoformat(),
        }
        for row in cursor.fetchall()
    ]

    # Query Fuel Prices
    cursor.execute(
        "SELECT fuel_type, price_syp, unit, last_updated FROM fuel_prices"
    )
    fuel = {
        row[0]: {
            "price": float(row[1]),
            "unit": row[2],
            "last_updated": row[3].isoformat(),
        }
        for row in cursor.fetchall()
    }

    return {
        "postgres_status": "Successfully Upserted",
        "exchange_rates": rates,
        "fuel_prices": fuel,
        "news_articles": news,
    }


if __name__ == "__main__":
    # Initialize Postgres Connection & Create Schema
    pg_connection = initialize_postgresql_db(DB_CONFIG)

    # Scrape Live Data
    cbs_rates, cbs_news = scrape_central_bank_live()
    moe_news = scrape_ministry_electricity_live()
    fuel_rates = scrape_live_fuel_rates()

    # Execute UPSERT into PostgreSQL
    upsert_to_postgres(pg_connection, cbs_rates, cbs_news + moe_news, fuel_rates)

    # Query & Output JSON
    output_json = export_postgres_to_json(pg_connection)
    print(json.dumps(output_json, indent=2, ensure_ascii=False))

    pg_connection.close()