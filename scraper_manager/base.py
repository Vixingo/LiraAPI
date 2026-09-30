"""
scraper_manager/base.py

Shared utilities: DB config from environment, connection helpers,
retry decorator, and structured logging.
"""

import logging
import os
import time
from functools import wraps
from typing import Any

import psycopg2

# ── logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


# ── DB config ──────────────────────────────────────────────────────────────────

def db_config() -> dict[str, Any]:
    """
    Returns psycopg2 connection kwargs sourced entirely from environment
    variables — no credentials are hardcoded here.

    Inside Docker the compose file injects DATABASE_URL, so all services
    connect to the ``postgres`` container automatically.  For local dev
    outside Docker, set the POSTGRES_* variables (or DATABASE_URL) in .env.
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return {"dsn": database_url}

    password = os.getenv("POSTGRES_PASSWORD")
    if not password:
        raise RuntimeError(
            "No database credentials found. "
            "Set DATABASE_URL or POSTGRES_PASSWORD in the environment."
        )

    return {
        "dbname":   os.getenv("POSTGRES_DB",   "postgres"),
        "user":     os.getenv("POSTGRES_USER", "postgres"),
        "password": password,
        "host":     os.getenv("POSTGRES_HOST", "postgres"),   # service name in Docker
        "port":     os.getenv("POSTGRES_PORT", "5432"),
    }


def get_connection() -> psycopg2.extensions.connection:
    """Open and return a new psycopg2 connection using :func:`db_config`."""
    return psycopg2.connect(**db_config())


# ── retry decorator ────────────────────────────────────────────────────────────

def with_retry(max_attempts: int = 3, delay: float = 2.0, backoff: float = 2.0):
    """
    Decorator that retries a function up to *max_attempts* times on exception,
    with exponential back-off starting at *delay* seconds.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            log = get_logger(fn.__module__)
            wait = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as exc:
                    if attempt == max_attempts:
                        log.error(
                            "%s: all %d attempts failed — %s",
                            fn.__name__, max_attempts, exc,
                        )
                        raise
                    log.warning(
                        "%s: attempt %d/%d failed (%s) — retrying in %.1fs",
                        fn.__name__, attempt, max_attempts, exc, wait,
                    )
                    time.sleep(wait)
                    wait *= backoff
        return wrapper
    return decorator
