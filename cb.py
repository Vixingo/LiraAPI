import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime

def scrape_syrian_central_bank_rates():
    url = "https://cb.gov.sy/"
    
    # Send request with a standard browser User-Agent
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching the webpage: {e}")
        return None

    # Parse HTML using BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')
    
    rates_data = []

    # 1. Identify rate blocks on the home page
    # The rates container includes currency code, value, and net daily change
    items = soup.find_all(class_=lambda x: x and 'currency' in x.lower()) if soup.find_all(class_=lambda x: x and 'currency' in x.lower()) else []

    # Fallback text-based extraction matching site layout structure
    raw_text = soup.get_text()
    
    # Targeted text extraction strategy for predictable structure
    currencies = [
        {"code": "KWD", "name": "Kuwaiti Dinar / الدينار الكويتي"},
        {"code": "USD", "name": "US Dollar / الدولار الأمريكي"},
        {"code": "SEK", "name": "Swedish Krona / كرونة سويدية"},
        {"code": "AED", "name": "UAE Dirham / الدرهم الإماراتي"},
        {"code": "GBP", "name": "British Pound / جنيه استرليني"},
        {"code": "JOD", "name": "Jordanian Dinar / الدينار الأردني"},
        {"code": "EUR", "name": "Euro / يورو"},
        {"code": "SAR", "name": "Saudi Riyal / الريال السعودي"}
    ]

    print("--- Central Bank of Syria: Exchange Rate Extractor ---")
    print(f"Extraction Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Parse text elements around currency tokens
    for curr in currencies:
        code = curr["code"]
        if code in raw_text:
            try:
                # Find occurrences of the currency code block
                parts = raw_text.split(code)
                if len(parts) > 1:
                    # Tokenize the vicinity following the currency code
                    sub_tokens = parts[1].split()[:2]
                    rate = float(sub_tokens[0].replace(',', ''))
                    change = float(sub_tokens[1]) if len(sub_tokens) > 1 else 0.0
                    
                    rates_data.append({
                        "Currency Name": curr["name"],
                        "Currency Code": code,
                        "Exchange Rate (SYP)": rate,
                        "Daily Change": change
                    })
            except (IndexError, ValueError):
                continue

    # Convert to Pandas DataFrame for easy export/manipulation
    df = pd.DataFrame(rates_data)
    return df

if __name__ == "__main__":
    df_rates = scrape_syrian_central_bank_rates()
    
    if df_rates is not None and not df_rates.empty:
        print(df_rates.to_string(index=False))
        
        # Export options
        # df_rates.to_csv("syria_exchange_rates.csv", index=False, encoding='utf-8-sig')
        # df_rates.to_json("syria_exchange_rates.json", orient="records", indent=4)
    else:
        print("No exchange rate data could be extracted.")