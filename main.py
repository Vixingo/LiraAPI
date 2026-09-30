import os
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterator

import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="Market Data API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("FRONTEND_URL", "*").split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _database_options() -> dict[str, Any]:
    """Build connection options without requiring a database at import time."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return {"dsn": database_url}

    return {
        "dbname": os.getenv("POSTGRES_DB", "postgres"),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "Vixingo"),
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
    }


@contextmanager
def database_connection() -> Iterator[Any]:
    connection = psycopg2.connect(**_database_options())
    try:
        yield connection
    finally:
        connection.close()


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _fetch_market_data(connection: Any) -> dict[str, Any]:
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT currency_code, rate_syp, last_updated "
            "FROM exchange_rates ORDER BY currency_code"
        )
        rates = {
            row[0]: {
                "rate_syp": _json_value(row[1]),
                "last_updated": _json_value(row[2]),
            }
            for row in cursor.fetchall()
        }

        cursor.execute(
            "SELECT fuel_type, price_syp, unit, last_updated "
            "FROM fuel_prices ORDER BY fuel_type"
        )
        fuel_prices = {
            row[0]: {
                "price": _json_value(row[1]),
                "unit": row[2],
                "last_updated": _json_value(row[3]),
            }
            for row in cursor.fetchall()
        }

        cursor.execute(
            "SELECT source_name, title, category, source_url, last_updated "
            "FROM news_articles ORDER BY last_updated DESC"
        )
        news_articles = [
            {
                "source": row[0],
                "title": row[1],
                "category": row[2],
                "url": row[3],
                "last_updated": _json_value(row[4]),
            }
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()

    return {
        "status": "success",
        "exchange_rates": rates,
        "fuel_prices": fuel_prices,
        "news_articles": news_articles,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/market")
def market_data() -> dict[str, Any]:
    try:
        with database_connection() as connection:
            return _fetch_market_data(connection)
    except psycopg2.Error as error:
        raise HTTPException(status_code=503, detail="Market data is unavailable") from error


@app.get("/api/v1/market/{category}")
def market_category(category: str) -> Any:
    category_map = {
        "exchange-rates": "exchange_rates",
        "fuel-prices": "fuel_prices",
        "news": "news_articles",
    }
    key = category_map.get(category.lower())
    if key is None:
        raise HTTPException(status_code=404, detail="Unknown market data category")

    data = market_data()
    return {"status": data["status"], key: data[key]}