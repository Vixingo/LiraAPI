import re
import requests
from bs4 import BeautifulSoup

_URL = "https://allira-sy.com/en/gold"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


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
        return None

    text_content = karat_21_section.get_text(separator=" ", strip=True)

    buy_match = re.search(r"Buy\s*([\d,]+)", text_content, re.IGNORECASE)
    sell_match = re.search(r"Sell\s*([\d,]+)", text_content, re.IGNORECASE)

    return {
        "buy": int(buy_match.group(1).replace(",", "")) if buy_match else None,
        "sell": int(sell_match.group(1).replace(",", "")) if sell_match else None,
    }


if __name__ == "__main__":
    data = scrape_gold_prices()
    if data:
        print("--- 21 Karat Gold Prices ---")
        print(f"Buy Price : {data['buy']} SYP/g")
        print(f"Sell Price: {data['sell']} SYP/g")
    else:
        print("Could not locate the 21 Karat section on the page.")