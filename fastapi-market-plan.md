# FastAPI Market Data Service — Implementation Plan

## Goal

Build a Python-based data pipeline that scrapes market data, stores it in PostgreSQL,
and serves it to the frontend via a FastAPI service running alongside the existing Node backend.

---

## Architecture

```
Scrapers (Python, scheduled)
        │
        ▼
  PostgreSQL DB
        │
        ▼
  FastAPI Service  ◄──── Frontend (React / Next.js)
        │
  (optional) Redis Cache
```

The Node.js backend continues to run unchanged. FastAPI handles only the new scraper-fed routes.
Nginx routes traffic to whichever service owns a given path prefix.

---

## Phase 1 — Database Schema

Design the schema before writing any scraper. All scrapers write to the same tables.

### `market_assets` — latest snapshot per symbol

```sql
CREATE TABLE market_assets (
    id          SERIAL PRIMARY KEY,
    symbol      VARCHAR(20)    NOT NULL,
    asset_name  VARCHAR(128),
    category    VARCHAR(32),        -- forex | crypto | metals | energy | food | stocks
    price_usd   NUMERIC(20, 8),
    price_syp   NUMERIC(20, 4),
    change_24h  NUMERIC(10, 4),
    volume      NUMERIC(20, 2),
    source      VARCHAR(64),        -- which scraper populated this row
    recorded_at TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    UNIQUE (symbol, source)         -- one row per symbol per source
);

CREATE INDEX idx_market_assets_symbol      ON market_assets(symbol);
CREATE INDEX idx_market_assets_category    ON market_assets(category);
CREATE INDEX idx_market_assets_recorded_at ON market_assets(recorded_at DESC);
```

### `market_ticks` — historical time-series

```sql
CREATE TABLE market_ticks (
    id          BIGSERIAL PRIMARY KEY,
    symbol      VARCHAR(20)    NOT NULL,
    price_usd   NUMERIC(20, 8),
    price_syp   NUMERIC(20, 4),
    recorded_at TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_market_ticks_symbol_time ON market_ticks(symbol, recorded_at DESC);
```

---

## Phase 2 — Scrapers

Each scraper is an independent Python module. They run on a schedule (APScheduler or
a simple asyncio loop) and are completely decoupled from the API layer.

### Project Structure

```
lira-scrapers/
├── scrapers/
│   ├── __init__.py
│   ├── base.py              # shared DB pool, retry logic, logging
│   ├── binance_scraper.py
│   ├── forex_scraper.py
│   ├── metals_scraper.py
│   └── cbos_scraper.py
├── scheduler.py             # runs all scrapers on their intervals
├── requirements.txt
└── .env
```

### Base Scraper Pattern

```python
# scrapers/base.py
import asyncpg, logging

logger = logging.getLogger(__name__)
pool: asyncpg.Pool = None

async def get_pool(dsn: str) -> asyncpg.Pool:
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(dsn)
    return pool

async def upsert_asset(conn, record: dict):
    await conn.execute("""
        INSERT INTO market_assets
            (symbol, asset_name, category, price_usd, price_syp, change_24h, volume, source)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ON CONFLICT (symbol, source) DO UPDATE SET
            price_usd   = EXCLUDED.price_usd,
            price_syp   = EXCLUDED.price_syp,
            change_24h  = EXCLUDED.change_24h,
            volume      = EXCLUDED.volume,
            recorded_at = NOW()
    """,
        record["symbol"], record["asset_name"], record["category"],
        record["price_usd"], record.get("price_syp"), record.get("change_24h"),
        record.get("volume"), record["source"]
    )
```

### Example: Binance Crypto Scraper

```python
# scrapers/binance_scraper.py
import httpx
from .base import get_pool, upsert_asset

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

async def run(dsn: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.binance.com/api/v3/ticker/24hr",
            params={"symbols": str(SYMBOLS)}
        )
        tickers = resp.json()

    pool = await get_pool(dsn)
    async with pool.acquire() as conn:
        for t in tickers:
            await upsert_asset(conn, {
                "symbol":     t["symbol"].replace("USDT", ""),
                "asset_name": t["symbol"],
                "category":   "crypto",
                "price_usd":  float(t["lastPrice"]),
                "change_24h": float(t["priceChangePercent"]),
                "volume":     float(t["volume"]),
                "source":     "binance"
            })
```

### Scheduler

```python
# scheduler.py
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from scrapers import binance_scraper, forex_scraper

DSN = "postgresql://user:pass@localhost/lira_live"

scheduler = AsyncIOScheduler()
scheduler.add_job(lambda: asyncio.create_task(binance_scraper.run(DSN)), "interval", seconds=30)
scheduler.add_job(lambda: asyncio.create_task(forex_scraper.run(DSN)),   "interval", minutes=5)

if __name__ == "__main__":
    scheduler.start()
    asyncio.get_event_loop().run_forever()
```

---

## Phase 3 — FastAPI Service

### Project Structure

```
lira-fastapi/
├── main.py
├── database.py
├── models.py
├── routers/
│   ├── market.py
│   └── history.py
├── middleware/
│   └── api_key.py
├── requirements.txt
└── .env
```

### `database.py` — Async Connection Pool

```python
import asyncpg
from typing import AsyncGenerator

pool: asyncpg.Pool = None

async def init_db(dsn: str):
    global pool
    pool = await asyncpg.create_pool(dsn)

async def get_db() -> AsyncGenerator:
    async with pool.acquire() as conn:
        yield conn
```

### `models.py` — Pydantic Response Shapes

These are the exact shapes the frontend receives.

```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class AssetResponse(BaseModel):
    symbol:      str
    asset_name:  str
    category:    str
    price_usd:   float
    price_syp:   Optional[float]
    change_24h:  float
    volume:      Optional[float]
    source:      str
    recorded_at: datetime

class PaginatedResponse(BaseModel):
    status:     str = "success"
    category:   str
    count:      int
    page:       int
    limit:      int
    total:      int
    data:       List[AssetResponse]

class TickPoint(BaseModel):
    timestamp: datetime
    price_usd: float
    price_syp: Optional[float]

class HistoryResponse(BaseModel):
    status:       str = "success"
    symbol:       str
    interval:     str
    points_count: int
    history:      List[TickPoint]
```

### `routers/market.py` — Category & Single Asset Endpoints

```python
from fastapi import APIRouter, Depends, Query, HTTPException
from database import get_db
from models import PaginatedResponse, AssetResponse

router = APIRouter(prefix="/api/v1/market", tags=["market"])

@router.get("/{category}", response_model=PaginatedResponse)
async def get_category(
    category: str,
    page:  int = Query(default=1,  ge=1),
    limit: int = Query(default=20, le=100),
    db=Depends(get_db)
):
    offset = (page - 1) * limit

    total = await db.fetchval(
        "SELECT COUNT(DISTINCT symbol) FROM market_assets WHERE category = $1", category
    )

    rows = await db.fetch("""
        SELECT DISTINCT ON (symbol)
            symbol, asset_name, category, price_usd, price_syp,
            change_24h, volume, source, recorded_at
        FROM market_assets
        WHERE category = $1
        ORDER BY symbol, recorded_at DESC
        LIMIT $2 OFFSET $3
    """, category, limit, offset)

    return PaginatedResponse(
        category=category,
        count=len(rows),
        page=page,
        limit=limit,
        total=total,
        data=[dict(r) for r in rows]
    )


@router.get("/{category}/{symbol}", response_model=AssetResponse)
async def get_single_asset(category: str, symbol: str, db=Depends(get_db)):
    row = await db.fetchrow("""
        SELECT symbol, asset_name, category, price_usd, price_syp,
               change_24h, volume, source, recorded_at
        FROM market_assets
        WHERE category = $1 AND symbol = $2
        ORDER BY recorded_at DESC
        LIMIT 1
    """, category, symbol.upper())

    if not row:
        raise HTTPException(404, detail=f"{symbol} not found in {category}")

    return dict(row)
```

### `routers/history.py` — Time-Series Endpoint

```python
from fastapi import APIRouter, Depends, Query
from database import get_db
from models import HistoryResponse
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/market", tags=["history"])

INTERVAL_MAP = {
    "1h":  timedelta(hours=1),
    "1d":  timedelta(days=1),
    "7d":  timedelta(days=7),
    "30d": timedelta(days=30),
    "1y":  timedelta(days=365),
}

@router.get("/history/{symbol}", response_model=HistoryResponse)
async def get_history(
    symbol:   str,
    interval: str = Query(default="7d", regex="^(1h|1d|7d|30d|1y)$"),
    db=Depends(get_db)
):
    delta = INTERVAL_MAP[interval]
    since = datetime.utcnow() - delta

    rows = await db.fetch("""
        SELECT recorded_at AS timestamp, price_usd, price_syp
        FROM market_ticks
        WHERE symbol = $1 AND recorded_at >= $2
        ORDER BY recorded_at ASC
        LIMIT 500
    """, symbol.upper(), since)

    return HistoryResponse(
        symbol=symbol.upper(),
        interval=interval,
        points_count=len(rows),
        history=[dict(r) for r in rows]
    )
```

### `main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import init_db
from routers import market, history
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(os.getenv("DATABASE_URL"))
    yield

app = FastAPI(title="Lira Live Market API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "*")],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(market.router)
app.include_router(history.router)
```

---

## Phase 4 — Nginx Routing (Coexistence with Node)

Route by path prefix so the frontend hits one unified API:

```nginx
# nginx/nginx.conf

upstream node_backend   { server node:3000; }
upstream fastapi_backend { server fastapi:8000; }

server {
    listen 443 ssl;

    # New Python scraper-fed routes → FastAPI
    location /api/v1/market/ {
        proxy_pass http://fastapi_backend;
    }

    # Everything else → existing Node backend
    location /api/v1/ {
        proxy_pass http://node_backend;
    }
}
```

---

## Phase 5 — Docker Setup

Add a FastAPI service and scheduler service to `docker-compose.yml`:

```yaml
services:
  fastapi:
    build: ./lira-fastapi
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://user:pass@db/lira_live
      FRONTEND_URL: https://your-frontend.com
    command: uvicorn main:app --host 0.0.0.0 --port 8000
    depends_on:
      - db

  scrapers:
    build: ./lira-scrapers
    environment:
      DATABASE_URL: postgresql://user:pass@db/lira_live
    command: python scheduler.py
    depends_on:
      - db
```

---

## Dependencies

### FastAPI service (`lira-fastapi/requirements.txt`)
```
fastapi==0.115.0
uvicorn[standard]==0.30.6
asyncpg==0.29.0
pydantic==2.9.2
python-dotenv==1.0.1
```

### Scrapers (`lira-scrapers/requirements.txt`)
```
httpx==0.27.2
asyncpg==0.29.0
apscheduler==3.10.4
python-dotenv==1.0.1
```

---

## Delivery Checklist

- [ ] Phase 1 — Run schema migrations on Postgres
- [ ] Phase 2 — Write and test scrapers locally, verify rows appear in DB
- [ ] Phase 3 — Build FastAPI app, verify `/docs` auto-generated UI works
- [ ] Phase 4 — Update Nginx config to route `/api/v1/market/` to FastAPI
- [ ] Phase 5 — Add services to `docker-compose.yml` and test full stack
- [ ] Optional — Add Redis caching layer in front of DB reads (same pattern as Node backend)
- [ ] Optional — Add API key middleware to FastAPI (`Depends()`) to match Node auth model

---

## Notes

- **Scrapers are completely separate from the API.** They write to DB; FastAPI only reads. No coupling.
- **The Node backend is untouched.** FastAPI owns only the new `/api/v1/market/` path prefix.
- **`DISTINCT ON (symbol)`** in queries ensures the frontend always gets the freshest row per symbol, not duplicates from multiple scrape cycles.
- **Free vs paid tier chart data** — if needed, add an API key middleware (`middleware/api_key.py`) that sets `request.state.tier` and gate `history` endpoints behind it.
