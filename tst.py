import requests
import psycopg2
from datetime import datetime


DB_CONFIG = {
    "dbname": "postgres",
    "user": "postgres",
    "password": "Vixingo",
    "host": "localhost",
    "port": "5432"
}


def ensure_prices_table():
    create_table_query = """
    CREATE TABLE IF NOT EXISTS prices (
        symbol TEXT PRIMARY KEY,
        current_price NUMERIC NOT NULL,
        previous_price NUMERIC NOT NULL,
        change_percent TEXT NOT NULL,
        source TEXT NOT NULL,
        last_updated TIMESTAMP NOT NULL
    );
    """

    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute(create_table_query)
        conn.commit()


def calculate_percent_change(current_price: float, previous_price: float) -> float:

    if previous_price == 0:
        return 0.0
    prcnt = ((current_price - previous_price) / previous_price) * 100
    prcnt = round(prcnt, 2)

    print(prcnt)
    return  prcnt



def getfrommetals():
    ensure_prices_table()

    cookies = {
        '__SP4_Shrt_v1': '',
    }

    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'origin': 'https://www.metalsdaily.com',
        'priority': 'u=1, i',
        'referer': 'https://www.metalsdaily.com/live-prices/',
        'sec-ch-ua': '"Microsoft Edge";v="153", "Not_A Brand";v="8", "Chromium";v="153"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36 Edg/153.0.0.0',
        'x-requested-with': 'XMLHttpRequest',
        # 'cookie': '__SP4_Shrt_v1=',
    }

    data = {
        'com': 'XAUUSD|XAUGBP|XAUEUR|XAGUSD|XPTUSD|XPDUSD|XAUAUD|XAUCAD|XAUCHF|XAUJPY1G|XAUAED|XAUAED1G|XAUCNY|XAUCNY1G|XAUINR|XAUINR10|XAUZAR|XAURUB|XAUXAGUSD|XPTXPDUSD|XAGGBP|XAGEUR|USDGBP|GBPUSD|USDEUR|EURUSD|USDCHF|CHFUSD|USDJPY|USDRUB|USDHKD|USDMXN|USDNOK|USDNZD|USDPLN|USDSEK|USDSGD|USDTRY|USDZAR|BTCUSD',
    }

    response = requests.post('https://www.metalsdaily.com/__dta/pd.ashx', cookies=cookies, headers=headers, data=data)

    



    obj = response.json()["p"]


    for curr in obj:
        symbol = curr["a"]
        new_price = float(curr["b"])
        source = "Metals.live"


        select_query = "SELECT current_price FROM prices WHERE symbol = %s;"
        
        upsert_query = """
        INSERT INTO prices (symbol, current_price, previous_price, change_percent, source, last_updated)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (symbol) 
        DO UPDATE SET
            previous_price = EXCLUDED.previous_price,
            current_price = EXCLUDED.current_price,
            change_percent = EXCLUDED.change_percent,
            source = EXCLUDED.source,
            last_updated = EXCLUDED.last_updated;
        """

        try:
            with psycopg2.connect(**DB_CONFIG) as conn:
                with conn.cursor() as cur:
                    # 1. Fetch the existing current_price to use as previous_price
                    cur.execute(select_query, (symbol,))
                    row = cur.fetchone()

                    if row and row[0] is not None:
                        previous_price = float(row[0])
                        # Calculate percentage change based on fetched previous_price
                        change_pct = ((new_price - previous_price) / previous_price) * 100
                        change_percent_str = f"{change_pct:.2f}%"
                    else:
                        # New record fallback (no existing price yet)
                        previous_price = new_price
                        change_percent_str = "0.00%"

                    # 2. Execute upsert with newly calculated values
                    now = datetime.now()
                    cur.execute(
                        upsert_query,
                        (
                            symbol,
                            new_price,
                            previous_price,
                            change_percent_str,
                            source,
                            now
                        )
                    )
                conn.commit()
                print(f"[{symbol}] Updated -> Current: {new_price}, Previous: {previous_price}, Change: {change_percent_str}")

        except Exception as e:
            print(f"Error processing record for {symbol}: {e}")




def getfrombinance():

    cookies = {
        'aws-waf-token': 'b06c7620-4fdc-4bc2-a670-ac9df7657566:BgoAbKsCZLvDHgAA:u+WsFFKHDi6l4Aeaa+ybZksQYbbijgClbD/k5NilwMl2ePlSUsx3TASEyXdMFnmdFqab2CWk69wxlrPKZRAsKNjkNEJOhdm1b/pgj3wHJgGR7yakgrehWjhQkyp6c7fGjcM85zunMKI/Ff74Z2xh5KEHHiNxb3AcoOkskky7Xkjmb23tAxH7riosEQZiUJQhu88pfvBT6VovkDl0c32vzF6ts8hZJkhWZtfi22P8lkCUZ62tiVhqD/6PaWZD6Qwpd9YiJft58tvn1knGX51rZZDNJ+NQzzkKkvo/NaCyOWh48DRJNk7Fm1lPbdsMhAgwbs9wZ/Vv4CHl',
        'theme': 'dark',
        'bnc-uuid': '66cf4252-df8f-40e6-8823-2365020f883b',
        'sajssdk_2015_cross_new_user': '1',
        'BNC_FV_KEY': '3327343dffdba1afa5bf29eddb48f0d707ba7a6b',
        'BNC_FV_KEY_T': '101-a6ALFC3arJ%2B9U20nqrd%2BwwdZImyIyfJ0jrztc2Lse8%2BUsnBVQkwMynYnS8B1UOEG1Tl8pUcqQWtvsK3ktQw3pw%3D%3D-SE0TGVnRBz0%2FJR2gPNxLww%3D%3D-ff',
        'BNC_FV_KEY_EXPIRE': '1790359140781',
        'sensorsdata2015jssdkcross': '%7B%22distinct_id%22%3A%221a0d86ee10c4e1-08547d93b34e2b8-4c657b58-1049088-1a0d86ee10d67c%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMWEwZDg2ZWUxMGM0ZTEtMDg1NDdkOTNiMzRlMmI4LTRjNjU3YjU4LTEwNDkwODgtMWEwZDg2ZWUxMGQ2N2MifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%7D',
        'OptanonConsent': 'groups=C0003%3A1%2CC0004%3A1%2CC0002%3A1%2CC0001%3A1&datestamp=2026-09-25T12%3A00%3A06.641Z&version=202506.1.0',
        'OptanonAlertBoxClosed': '2026-09-25T12:00:06.642Z',
    }

    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'max-age=0',
        'priority': 'u=0, i',
        'sec-ch-ua': '"Microsoft Edge";v="153", "Not_A Brand";v="8", "Chromium";v="153"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'cross-site',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36 Edg/153.0.0.0',
        # 'cookie': 'aws-waf-token=b06c7620-4fdc-4bc2-a670-ac9df7657566:BgoAbKsCZLvDHgAA:u+WsFFKHDi6l4Aeaa+ybZksQYbbijgClbD/k5NilwMl2ePlSUsx3TASEyXdMFnmdFqab2CWk69wxlrPKZRAsKNjkNEJOhdm1b/pgj3wHJgGR7yakgrehWjhQkyp6c7fGjcM85zunMKI/Ff74Z2xh5KEHHiNxb3AcoOkskky7Xkjmb23tAxH7riosEQZiUJQhu88pfvBT6VovkDl0c32vzF6ts8hZJkhWZtfi22P8lkCUZ62tiVhqD/6PaWZD6Qwpd9YiJft58tvn1knGX51rZZDNJ+NQzzkKkvo/NaCyOWh48DRJNk7Fm1lPbdsMhAgwbs9wZ/Vv4CHl; theme=dark; bnc-uuid=66cf4252-df8f-40e6-8823-2365020f883b; sajssdk_2015_cross_new_user=1; BNC_FV_KEY=3327343dffdba1afa5bf29eddb48f0d707ba7a6b; BNC_FV_KEY_T=101-a6ALFC3arJ%2B9U20nqrd%2BwwdZImyIyfJ0jrztc2Lse8%2BUsnBVQkwMynYnS8B1UOEG1Tl8pUcqQWtvsK3ktQw3pw%3D%3D-SE0TGVnRBz0%2FJR2gPNxLww%3D%3D-ff; BNC_FV_KEY_EXPIRE=1790359140781; sensorsdata2015jssdkcross=%7B%22distinct_id%22%3A%221a0d86ee10c4e1-08547d93b34e2b8-4c657b58-1049088-1a0d86ee10d67c%22%2C%22first_id%22%3A%22%22%2C%22props%22%3A%7B%22%24latest_traffic_source_type%22%3A%22%E7%9B%B4%E6%8E%A5%E6%B5%81%E9%87%8F%22%2C%22%24latest_search_keyword%22%3A%22%E6%9C%AA%E5%8F%96%E5%88%B0%E5%80%BC_%E7%9B%B4%E6%8E%A5%E6%89%93%E5%BC%80%22%2C%22%24latest_referrer%22%3A%22%22%7D%2C%22identities%22%3A%22eyIkaWRlbnRpdHlfY29va2llX2lkIjoiMWEwZDg2ZWUxMGM0ZTEtMDg1NDdkOTNiMzRlMmI4LTRjNjU3YjU4LTEwNDkwODgtMWEwZDg2ZWUxMGQ2N2MifQ%3D%3D%22%2C%22history_login_id%22%3A%7B%22name%22%3A%22%22%2C%22value%22%3A%22%22%7D%7D; OptanonConsent=groups=C0003%3A1%2CC0004%3A1%2CC0002%3A1%2CC0001%3A1&datestamp=2026-09-25T12%3A00%3A06.641Z&version=202506.1.0; OptanonAlertBoxClosed=2026-09-25T12:00:06.642Z',
    }

    params = {
       # 'symbol': 'BTCUSDT',
    }

    response = requests.get('https://api.binance.com/api/v3/ticker/24hr', params=params, cookies=cookies, headers=headers)
    #print(response.json())
    symbols = ["ETH","BTC","BNB","XRP"]
    for itm in response.json():
        for sym in symbols:
            if sym in itm["symbol"]:
                performDB(itm["symbol"],itm["bidPrice"],itm["lastPrice"],itm["priceChangePercent"],"Binance")

    #performDB("","","","","")


def performDB(symbol, current_price, previous_price, change_percent, source):
    ensure_prices_table()

    # Sample data record to upsert
    record = {
        "symbol": symbol,
        "current_price": current_price,
        "previous_price": previous_price,
        "change_percent": change_percent,
        "source": source
    }

    upsert_query = """
    INSERT INTO prices (symbol, current_price, previous_price, change_percent, source, last_updated)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (symbol) 
    DO UPDATE SET
        previous_price = prices.current_price, -- carry over existing current_price to previous_price
        current_price = EXCLUDED.current_price,
        change_percent = EXCLUDED.change_percent,
        source = EXCLUDED.source,
        last_updated = EXCLUDED.last_updated;
    """

    try:
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                now = datetime.now()
                cur.execute(
                    upsert_query,
                    (
                        record["symbol"],
                        record["current_price"],
                        record["previous_price"],
                        record["change_percent"],
                        record["source"],
                        now
                    )
                )
            conn.commit()
            print(f"Successfully upserted record for {record['symbol']}.")

    except Exception as e:
        print(f"Error executing upsert: {e}")

def getfromsptoday():

    print("")


def getfromLirascope():
   
    headers = {
        'sec-ch-ua-platform': '"Windows"',
        'Referer': 'https://lirascope.syria-cloud.sy/en',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36 Edg/153.0.0.0',
        'Accept': 'application/json, text/plain, */*',
        'X-ClientId': 'lirascope-frontend',
        'sec-ch-ua': '"Microsoft Edge";v="153", "Not_A Brand";v="8", "Chromium";v="153"',
        'sec-ch-ua-mobile': '?0',
    }


    currencies = ["USD","EUR","AED","AUD","BHD","BRL","CAD","CHF","DKK","DZD"]
    for currency in currencies:

        params = {
            'currency': currency,
            'source': 'MARKET',
            'days': '7',
            'lang': 'en',
        }

        response = requests.get('https://lirascope.syria-cloud.sy/api/v1/rates/history', params=params, headers=headers)

        obj = response.json()
        rates = obj.get("rates", [])
        if len(rates) < 2:
            print(f"Skipping {currency}: not enough historical rates")
            continue

        print(rates[0])
        print(rates[1])
        try:
            prcnt = calculate_percent_change(rates[0]["buy"], rates[1]["buy"])
            performDB(obj["currency"]+"_SYP", rates[0]["buy"], rates[1]["buy"], prcnt, "Lirascope")
        except:
            print("ERR")



def getfromsptoday():
 
    cookies = {
        'cf_country': 'PH',
        'cf_clearance': 'v3uxwN7ACllsAPFtCkB4n7tfzjJxNgHmJKrmDvf3PSE-1790399165-1.2.1.1-QKtspOcIWeXCgWkwGeyte8J2dFwWBaVK6KSKNBq8BL_E27cedCtosu_i.2fqZWQ3fioO6Ob4NBpOeKm_ZY22kMoIB5Pwq5yn_1xpb1M8YXDQAGcXwQ6vmEH2pSs9rt5f1edeZ1tuiFoNXhT6SXKKHHrdimwposXMNQExX9rcacLjWPTU8rLhIRcgFX1m3tjw1Z_YbApYIOLk3VOHJSd4HQZ29QuyYNYIck90oUGl96OsCq8UV6kpTMNw3_S05otgiIEkSXpKa4C39mbwilmc1xzfmAbC8NwuXNukATRGInKBY80SKAp3b0ab5urhjVdUWwWlZHccfVKj8xfD7plpCO7efDTzxmFCXm07cFlVRNU',
    }

    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'priority': 'u=1, i',
        'referer': 'https://www.sp-today.com/en/currency/us-dollar',
        'sec-ch-ua': '"Microsoft Edge";v="153", "Not_A Brand";v="8", "Chromium";v="153"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36 Edg/153.0.0.0',
        # 'cookie': 'cf_country=PH; cf_clearance=v3uxwN7ACllsAPFtCkB4n7tfzjJxNgHmJKrmDvf3PSE-1790399165-1.2.1.1-QKtspOcIWeXCgWkwGeyte8J2dFwWBaVK6KSKNBq8BL_E27cedCtosu_i.2fqZWQ3fioO6Ob4NBpOeKm_ZY22kMoIB5Pwq5yn_1xpb1M8YXDQAGcXwQ6vmEH2pSs9rt5f1edeZ1tuiFoNXhT6SXKKHHrdimwposXMNQExX9rcacLjWPTU8rLhIRcgFX1m3tjw1Z_YbApYIOLk3VOHJSd4HQZ29QuyYNYIck90oUGl96OsCq8UV6kpTMNw3_S05otgiIEkSXpKa4C39mbwilmc1xzfmAbC8NwuXNukATRGInKBY80SKAp3b0ab5urhjVdUWwWlZHccfVKj8xfD7plpCO7efDTzxmFCXm07cFlVRNU',
    }


    currencies = ["USD","EUR","AED","AUD","BHD","BRL","CAD","CHF","DKK","DZD"]
    for currency in currencies:
    

        params = {
            'code': currency,
            'city': 'damascus',
            'range': '1w',
        }

        response = requests.get('https://www.sp-today.com/api/historical', params=params, cookies=cookies, headers=headers)
        obj = response.json()

        prcnt = calculate_percent_change(obj[5]["buy"],obj[4]["buy"])
        performDB(currency+"_SYP",obj[5]["buy"],obj[4]["buy"],prcnt,"SP-Today")



def getfromtwelve():
   
   # response = requests.get("https://api.twelvedata.com/time_series?apikey=811415fe69264874a0de93be376c2c08&interval=1min&format=JSON&symbol=BTC/ETH")
   response = requests.get("https://api.twelvedata.com/time_series?apikey=811415fe69264874a0de93be376c2c08&interval=1min&format=JSON&symbol=BTC/ETH&type=stock")
   print(response.text)

getfromtwelve()    
getfromsptoday()
getfromLirascope()
getfrommetals()
getfrombinance()