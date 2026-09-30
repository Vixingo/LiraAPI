"""
scheduler.py — Runs all scrapers on a 30–60 second polling loop.

Each scraper runs in its own thread so a slow/failing source doesn't
block the others.  The interval is randomised per-cycle to avoid
hammering every source at the exact same second.

Usage:
    python scheduler.py
"""

import logging
import random
import threading
import time
from datetime import datetime

# ── scraper imports ────────────────────────────────────────────────────────────
from energy import (
    DB_CONFIG,
    initialize_postgresql_db,
    scrape_central_bank_live,
    scrape_ministry_electricity_live,
    scrape_live_fuel_rates,
    upsert_to_postgres,
)
from metals import scrape_gold_prices          # see note below
from news import fetch_articles, upsert_articles

# ── logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(threadName)s] %(levelname)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── constants ──────────────────────────────────────────────────────────────────
MIN_INTERVAL = 30   # seconds
MAX_INTERVAL = 60   # seconds

# ── individual scraper jobs ────────────────────────────────────────────────────

def job_energy():
    """Scrapes exchange rates, news, and fuel prices then upserts to Postgres."""
    log.info("energy: starting scrape")
    try:
        conn = initialize_postgresql_db(DB_CONFIG)
        cbs_rates, cbs_news = scrape_central_bank_live()
        moe_news = scrape_ministry_electricity_live()
        fuel_rates = scrape_live_fuel_rates()
        upsert_to_postgres(conn, cbs_rates, cbs_news + moe_news, fuel_rates)
        conn.close()
        log.info(
            "energy: done — %d rates, %d news items, %d fuel types",
            len(cbs_rates),
            len(cbs_news) + len(moe_news),
            len(fuel_rates),
        )
    except Exception:
        log.exception("energy: scrape failed")


def job_metals():
    """Scrapes 21-karat gold buy/sell prices."""
    log.info("metals: starting scrape")
    try:
        data = scrape_gold_prices()
        if data:
            log.info("metals: buy=%s sell=%s SYP/g", data.get("buy"), data.get("sell"))
        else:
            log.warning("metals: no data returned")
    except Exception:
        log.exception("metals: scrape failed")


def job_news():
    """Fetches Ministry of Energy articles and upserts to Postgres."""
    log.info("news: starting fetch")
    try:
        articles = fetch_articles()
        if articles:
            upsert_articles(articles)
            log.info("news: upserted %d articles", len(articles))
        else:
            log.warning("news: no articles returned")
    except Exception:
        log.exception("news: fetch failed")


# ── scheduler loop ─────────────────────────────────────────────────────────────

def run_job_in_thread(job_fn):
    """Launches a job function in a daemon thread so it doesn't block the loop."""
    t = threading.Thread(target=job_fn, name=job_fn.__name__, daemon=True)
    t.start()
    return t


def scheduler_loop(jobs: list, stop_event: threading.Event):
    """
    Main loop:
      1. Fire every job in its own thread.
      2. Wait for all threads to finish (or time out after MAX_INTERVAL).
      3. Sleep for a random interval before the next cycle.
    """
    cycle = 0
    while not stop_event.is_set():
        cycle += 1
        log.info("=== cycle %d started at %s ===", cycle, datetime.utcnow().isoformat())

        threads = [run_job_in_thread(job) for job in jobs]

        # Wait for all jobs to complete (cap at MAX_INTERVAL so we never fall
        # behind even if a scraper hangs)
        for t in threads:
            t.join(timeout=MAX_INTERVAL)

        interval = random.randint(MIN_INTERVAL, MAX_INTERVAL)
        log.info("=== cycle %d done — next run in %ds ===", cycle, interval)
        stop_event.wait(timeout=interval)

    log.info("Scheduler stopped.")


# ── entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    stop = threading.Event()

    try:
        scheduler_loop(
            jobs=[job_energy, job_metals, job_news],
            stop_event=stop,
        )
    except KeyboardInterrupt:
        log.info("Interrupt received — shutting down.")
        stop.set()
