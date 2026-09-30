# scraper_manager — all data-collection modules live here
from .energy import (
    initialize_postgresql_db,
    scrape_central_bank_live,
    scrape_ministry_electricity_live,
    scrape_live_fuel_rates,
    upsert_to_postgres,
)
from .metals import scrape_gold_prices
from .news import fetch_articles, upsert_articles
from .cb import scrape_syrian_central_bank_rates

__all__ = [
    "initialize_postgresql_db",
    "scrape_central_bank_live",
    "scrape_ministry_electricity_live",
    "scrape_live_fuel_rates",
    "upsert_to_postgres",
    "scrape_gold_prices",
    "fetch_articles",
    "upsert_articles",
    "scrape_syrian_central_bank_rates",
]
