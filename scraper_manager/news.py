"""
scraper_manager/news.py

Fetches news articles from the Syrian Ministry of Energy API and
upserts them into PostgreSQL.
"""

import requests
from psycopg2.extras import Json

from .base import db_config, get_connection, get_logger, with_retry

log = get_logger(__name__)

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


@with_retry(max_attempts=3, delay=2.0)
def fetch_articles() -> list:
    """Fetch articles JSON from the Syrian Ministry of Energy API."""
    log.info("fetch_articles: requesting %s", API_URL)
    response = requests.get(API_URL, params=PARAMS, headers=HEADERS, timeout=15)
    response.raise_for_status()

    payload = response.json()

    if isinstance(payload, dict):
        articles = payload.get("data", payload.get("articles", []))
    elif isinstance(payload, list):
        articles = payload
    else:
        articles = []

    log.info("fetch_articles: retrieved %d articles", len(articles))
    return articles


def upsert_articles(articles: list) -> None:
    """
    Upsert a list of article dicts into the ``articles`` table,
    creating the table first if it does not exist.
    """
    if not articles:
        log.info("upsert_articles: nothing to upsert")
        return

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id         SERIAL PRIMARY KEY,
                article_id VARCHAR(100) UNIQUE,
                title      TEXT,
                body       TEXT,
                slug       TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                raw_json   JSONB
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
            article_id = str(item.get("id") or item.get("uuid") or item.get("slug"))
            title      = item.get("title") or item.get("name") or item.get("header", "")
            body       = item.get("body") or item.get("content") or item.get("description", "")
            slug       = item.get("slug", "")
            cursor.execute(insert_query, (article_id, title, body, slug, Json(item)))

        conn.commit()
        log.info("upsert_articles: upserted %d articles", len(articles))
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
