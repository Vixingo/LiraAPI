import json
import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json
import requests

# 1. API Configuration
API_URL = "https://web-api.moenergy.gov.sy/api/en/articles"
PARAMS = {
    "current_page": 1,
    "page": 1,
    "per_page": 12,
    "last_page": 1,
    "total": 0,
    "from": 0,
    "to": 0,
}
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# 2. PostgreSQL Connection Settings
DB_CONFIG = {
    "dbname": "postgres",
    "user": "postgres",
    "password": "Vixingo",
    "host": "localhost",
    "port": 5432,
}


def fetch_articles():
    """Fetch articles JSON from the Syrian Ministry of Energy API."""
    print("Fetching data from API...")
    response = requests.get(
        API_URL, params=PARAMS, headers=HEADERS, timeout=15
    )
    response.raise_for_status()

    payload = response.json()

    # Handles common API response wrappers (e.g., {'data': [...]} or raw array)
    if isinstance(payload, dict):
        return payload.get("data", payload.get("articles", []))
    elif isinstance(payload, list):
        return payload
    return []


def setup_and_insert():
    articles = fetch_articles()
    print(articles)

    if not articles:
        print("No articles found in the API response.")
        return

    print(f"Retrieved {len(articles)} articles.")

    # Connect to PostgreSQL
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        # Create table if it doesn't exist
        # Adjust or add fields as needed based on the exact keys returned by the API
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id SERIAL PRIMARY KEY,
                article_id VARCHAR(100) UNIQUE,
                title TEXT,
                body TEXT,
                slug TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                raw_json JSONB
            );
        """
        )

        # Upsert query: Inserts new records, or updates on unique key conflict (article_id)
        insert_query = """
            INSERT INTO articles (article_id, title, body, slug, raw_json)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (article_id) 
            DO UPDATE SET
                title = EXCLUDED.title,
                body = EXCLUDED.body,
                slug = EXCLUDED.slug,
                raw_json = EXCLUDED.raw_json;
        """

        inserted_count = 0
        for item in articles:
            # Safely extract common article keys with fallbacks
            article_id = str(
                item.get("id") or item.get("uuid") or item.get("slug")
            )
            title = (
                item.get("title") or item.get("name") or item.get("header", "")
            )
            body = (
                item.get("body")
                or item.get("content")
                or item.get("description", "")
            )
            slug = item.get("slug", "")

            cursor.execute(
                insert_query,
                (
                    article_id,
                    title,
                    body,
                    slug,
                    Json(item),  # Stores full raw JSON payload in a JSONB column
                ),
            )
            inserted_count += 1

        # Commit transaction
        conn.commit()
        print(
            f"Successfully saved {inserted_count} articles to PostgreSQL database."
        )

    except Exception as e:
        conn.rollback()
        print(f"Error executing database operation: {e}")
    finally:
        cursor.close()
        conn.close()


def upsert_articles(articles: list) -> None:
    """
    Upsert a list of article dicts (as returned by ``fetch_articles``) into
    the ``articles`` table, creating the table first if it does not exist.
    """
    if not articles:
        return

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id SERIAL PRIMARY KEY,
                article_id VARCHAR(100) UNIQUE,
                title TEXT,
                body TEXT,
                slug TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                raw_json JSONB
            );
            """
        )

        insert_query = """
            INSERT INTO articles (article_id, title, body, slug, raw_json)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (article_id)
            DO UPDATE SET
                title    = EXCLUDED.title,
                body     = EXCLUDED.body,
                slug     = EXCLUDED.slug,
                raw_json = EXCLUDED.raw_json;
        """

        for item in articles:
            article_id = str(
                item.get("id") or item.get("uuid") or item.get("slug")
            )
            title = item.get("title") or item.get("name") or item.get("header", "")
            body = (
                item.get("body")
                or item.get("content")
                or item.get("description", "")
            )
            slug = item.get("slug", "")
            cursor.execute(insert_query, (article_id, title, body, slug, Json(item)))

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    setup_and_insert()