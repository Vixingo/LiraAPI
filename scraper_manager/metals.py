"""
scraper_manager/metals.py

Scrapes 21-karat gold buy/sell prices from allira-sy.com.
"""

import re

import requests
from bs4 import BeautifulSoup

from .base import get_logger, with_retry

log = get_logger(__name__)

_URL = "https://allira-sy.com/en/gold"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


@with_retry(max_attempts=3, delay=2.0)
def scrape_gold_prices() -> dict | None:
    """
    Fetches 21-karat gold buy/sell prices from allira-sy.com.

    Returns a dict like ``{"buy": 1234567, "sell": 1230000}`` on success,
    or ``None`` if the section cannot be located.
    """
    response = requests.get(_URL, headers=_HEADERS, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    karat_21_section = None
    for element in soup.find_all(["div", "section", "tr", "td"]):
        if "21 Karat" in element.text:
            karat_21_section = element
            break

    if not karat_21_section:
        log.warning("scrape_gold_prices: 21 Karat section not found")
        return None

    text_content = karat_21_section.get_text(separator=" ", strip=True)

    buy_match  = re.search(r"Buy\s*([\d,]+)",  text_content, re.IGNORECASE)
    sell_match = re.search(r"Sell\s*([\d,]+)", text_content, re.IGNORECASE)

    result = {
        "buy":  int(buy_match.group(1).replace(",", ""))  if buy_match  else None,
        "sell": int(sell_match.group(1).replace(",", "")) if sell_match else None,
    }
    log.info("scrape_gold_prices: buy=%s sell=%s SYP/g", result["buy"], result["sell"])
    return result
