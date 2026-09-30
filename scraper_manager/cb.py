"""
scraper_manager/cb.py

Scrapes exchange rates from the Syrian Central Bank website (cb.gov.sy)
and returns a Pandas DataFrame.
"""

import re
from datetime import datetime

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .base import get_logger, with_retry

log = get_logger(__name__)

_CURRENCIES = [
    {"code": "KWD", "name": "Kuwaiti Dinar / الدينار الكويتي"},
    {"code": "USD", "name": "US Dollar / الدولار الأمريكي"},
    {"code": "SEK", "name": "Swedish Krona / كرونة سويدية"},
    {"code": "AED", "name": "UAE Dirham / الدرهم الإماراتي"},
    {"code": "GBP", "name": "British Pound / جنيه استرليني"},
    {"code": "JOD", "name": "Jordanian Dinar / الدينار الأردني"},
    {"code": "EUR", "name": "Euro / يورو"},
    {"code": "SAR", "name": "Saudi Riyal / الريال السعودي"},
]


@with_retry(max_attempts=3, delay=2.0)
def scrape_syrian_central_bank_rates() -> pd.DataFrame | None:
    """
    Scrapes the Central Bank of Syria homepage for foreign exchange rates.

    Returns a Pandas DataFrame with columns:
      Currency Name | Currency Code | Exchange Rate (SYP) | Daily Change
    or ``None`` if the request fails.
    """
    url = "https://cb.gov.sy/"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    raw_text = soup.get_text()

    rates_data = []
    log.info("scrape_syrian_central_bank_rates: parsing page (%d chars)", len(raw_text))

    for curr in _CURRENCIES:
        code = curr["code"]
        if code not in raw_text:
            continue
        try:
            parts = raw_text.split(code)
            if len(parts) > 1:
                sub_tokens = parts[1].split()[:2]
                rate   = float(sub_tokens[0].replace(",", ""))
                change = float(sub_tokens[1]) if len(sub_tokens) > 1 else 0.0
                rates_data.append(
                    {
                        "Currency Name":       curr["name"],
                        "Currency Code":       code,
                        "Exchange Rate (SYP)": rate,
                        "Daily Change":        change,
                    }
                )
        except (IndexError, ValueError):
            continue

    if not rates_data:
        log.warning("scrape_syrian_central_bank_rates: no rates found")
        return None

    df = pd.DataFrame(rates_data)
    log.info("scrape_syrian_central_bank_rates: extracted %d rates", len(df))
    return df
