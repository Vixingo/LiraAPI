"""
main.py — FastAPI Market Data Service

Architecture:
  Redis (TTL cache) → PostgreSQL (source of truth)

Every read endpoint checks Redis first. On a cache miss the DB is queried
and the result is written back to Redis with a configurable TTL.
"""

import json
import os
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterator

import psycopg2
import redis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# ── app ────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Market Data API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("FRONTEND_URL", "*").split(","),
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── Redis ──────────────────────────────────────────────────────────────────────

CACHE_TTL = int(os.getenv("CACHE_TTL_SECONDS", "30"))


def _get_redis() -> redis.Redis:
    """Return a Redis client from REDIS_URL (falls back to localhost)."""
    return redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def _cache_get(key: str) -> Any | None:
    """Return the cached value for *key*, or ``None`` on miss / Redis error."""
    try:
        raw = _get_redis().get(key)
        return json.loads(raw) if raw is not None else None
    except Exception:
        return None


def _cache_set(key: str, value: Any, ttl: int = CACHE_TTL) -> None:
    """Write *value* to Redis under *key* with the given TTL (seconds)."""
    try:
        _get_redis().setex(key, ttl, json.dumps(value, default=str))
    except Exception:
        pass  # cache is best-effort — never break a request over Redis


def _cache_invalidate(pattern: str) -> None:
    """Delete all keys matching *pattern* (e.g. ``'market:*'``)."""
    try:
        r = _get_redis()
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
    except Exception:
        pass


# ── PostgreSQL ─────────────────────────────────────────────────────────────────

def _database_options() -> dict[str, Any]:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return {"dsn": database_url}
    return {
        "dbname":   os.getenv("POSTGRES_DB",       "postgres"),
        "user":     os.getenv("POSTGRES_USER",     "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "Vixingo"),
        "host":     os.getenv("POSTGRES_HOST",     "localhost"),
        "port":     os.getenv("POSTGRES_PORT",     "5432"),
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


# ── DB query helpers ───────────────────────────────────────────────────────────

def _fetch_market_data(connection: Any) -> dict[str, Any]:
    cursor = connection.cursor()
    try:
        cursor.execute(
            "SELECT currency_code, rate_syp, last_updated "
            "FROM exchange_rates ORDER BY currency_code"
        )
        rates = {
            row[0]: {
                "rate_syp":    _json_value(row[1]),
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
                "price":       _json_value(row[1]),
                "unit":        row[2],
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
                "source":      row[0],
                "title":       row[1],
                "category":    row[2],
                "url":         row[3],
                "last_updated": _json_value(row[4]),
            }
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()

    return {
        "status":        "success",
        "exchange_rates": rates,
        "fuel_prices":   fuel_prices,
        "news_articles": news_articles,
    }


# ── routes ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, Any]:
    """Liveness probe — also reports Redis and DB reachability."""
    redis_ok = False
    db_ok = False

    try:
        _get_redis().ping()
        redis_ok = True
    except Exception:
        pass

    try:
        with database_connection() as conn:
            conn.cursor().execute("SELECT 1")
        db_ok = True
    except Exception:
        pass

    return {
        "status": "ok",
        "redis":  "up" if redis_ok else "down",
        "db":     "up" if db_ok    else "down",
    }


@app.get("/api/v1/prices")
def get_prices(source: str | None = None) -> dict[str, Any]:
    """Return all rows from public.prices, optionally filtered by source."""
    cache_key = f"prices:{source or 'all'}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        with database_connection() as connection:
            cursor = connection.cursor()
            try:
                if source:
                    cursor.execute(
                        "SELECT symbol, current_price, previous_price, change_percent, source, last_updated "
                        "FROM public.prices WHERE source = %s ORDER BY last_updated DESC",
                        (source,),
                    )
                else:
                    cursor.execute(
                        "SELECT symbol, current_price, previous_price, change_percent, source, last_updated "
                        "FROM public.prices ORDER BY last_updated DESC"
                    )
                rows = cursor.fetchall()
            finally:
                cursor.close()
    except psycopg2.Error as error:
        raise HTTPException(status_code=503, detail="Prices data is unavailable") from error

    data = [
        {
            "symbol":         row[0],
            "current_price":  _json_value(row[1]),
            "previous_price": _json_value(row[2]),
            "change_percent": row[3],
            "source":         row[4],
            "last_updated":   _json_value(row[5]),
        }
        for row in rows
    ]
    result = {"status": "success", "count": len(data), "prices": data}
    _cache_set(cache_key, result)
    return result


@app.get("/api/v1/prices/{symbol}")
def get_price_by_symbol(symbol: str) -> dict[str, Any]:
    """Return the latest row for a single symbol from public.prices."""
    cache_key = f"prices:symbol:{symbol.upper()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        with database_connection() as connection:
            cursor = connection.cursor()
            try:
                cursor.execute(
                    "SELECT symbol, current_price, previous_price, change_percent, source, last_updated "
                    "FROM public.prices WHERE symbol = %s ORDER BY last_updated DESC LIMIT 1",
                    (symbol.upper(),),
                )
                row = cursor.fetchone()
            finally:
                cursor.close()
    except psycopg2.Error as error:
        raise HTTPException(status_code=503, detail="Prices data is unavailable") from error

    if row is None:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol.upper()}' not found")

    result = {
        "status":         "success",
        "symbol":         row[0],
        "current_price":  _json_value(row[1]),
        "previous_price": _json_value(row[2]),
        "change_percent": row[3],
        "source":         row[4],
        "last_updated":   _json_value(row[5]),
    }
    _cache_set(cache_key, result)
    return result


@app.get("/api/v1/market")
def market_data() -> dict[str, Any]:
    cache_key = "market:all"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        with database_connection() as connection:
            result = _fetch_market_data(connection)
    except psycopg2.Error as error:
        raise HTTPException(status_code=503, detail="Market data is unavailable") from error

    _cache_set(cache_key, result)
    return result


@app.get("/api/v1/market/{category}")
def market_category(category: str) -> Any:
    category_map = {
        "exchange-rates": "exchange_rates",
        "fuel-prices":    "fuel_prices",
        "news":           "news_articles",
    }
    key = category_map.get(category.lower())
    if key is None:
        raise HTTPException(status_code=404, detail="Unknown market data category")

    cache_key = f"market:{category}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    data = market_data()
    result = {"status": data["status"], key: data[key]}
    _cache_set(cache_key, result)
    return result
