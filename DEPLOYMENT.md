# Deployment Guide

## Architecture Overview

```
Internet
    │
    ▼
 Nginx (80/443)
    ├── /api/v1/market/*  →  FastAPI  :8000  (scraper-fed market data)
    └── /*                →  Node.js  :3000  (existing backend)
                                │
                         PostgreSQL :5432
                                │
                          Redis  :6379  (FastAPI read cache)

Scheduler (daemon) ──writes──▶ PostgreSQL
```

Six containers, one Docker network (`backend`), two named volumes (`postgres_data`, `redis_data`).

---

## Prerequisites

| Tool | Minimum version |
|---|---|
| Docker | 24.x |
| Docker Compose | v2.x (`docker compose` command) |
| A domain / server with ports 80 and 443 open | — |
| TLS certificate (Let's Encrypt recommended) | — |

---

## 1. Clone & configure

```bash
git clone <your-repo-url>
cd scraper

# Create your environment file from the template
cp .env.example .env
```

Open `.env` and set every value:

```bash
# Required — never commit this file
POSTGRES_PASSWORD=a_strong_random_password

# Your frontend origin (comma-separated if multiple)
FRONTEND_URL=https://your-frontend.com
```

All other values have safe defaults and can be left as-is for a first deploy.

---

## 2. TLS certificates

Nginx expects certs at `./nginx/certs/`. Create that directory and place your
certificate files there:

```
nginx/
└── certs/
    ├── fullchain.pem   ← full certificate chain
    └── privkey.pem     ← private key
```

### Option A — Let's Encrypt (recommended for production)

```bash
# Install certbot on the host
sudo apt install certbot

# Obtain a certificate (run before starting nginx)
sudo certbot certonly --standalone -d your-domain.com

# Symlink into the project
mkdir -p nginx/certs
sudo ln -s /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/certs/fullchain.pem
sudo ln -s /etc/letsencrypt/live/your-domain.com/privkey.pem  nginx/certs/privkey.pem
```

### Option B — Self-signed (local / staging only)

```bash
mkdir -p nginx/certs
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/certs/privkey.pem \
  -out    nginx/certs/fullchain.pem \
  -subj "/CN=localhost"
```

---

## 3. Wire up your Node.js backend

The `node` service in `docker-compose.yml` is a placeholder. Uncomment and
adjust the `volumes` and `command` lines to point at your existing Node source:

```yaml
node:
  volumes:
    - ../your-node-app:/app
  command: node server.js          # or: npm start
```

If your Node app is managed separately (e.g. already running on the host),
replace the `node` service with a plain host-network reference in nginx:

```nginx
upstream node_backend {
    server host-gateway:3000;    # Docker host
}
```

---

## 4. Build & start all services

```bash
# Build images and start everything in the background
docker compose up -d --build

# Tail logs to verify startup
docker compose logs -f
```

Expected healthy startup order: `postgres` → `redis` → `fastapi` → `scheduler` → `nginx`.

Verify the stack is running:

```bash
docker compose ps
```

All services should show `Up` or `Up (healthy)`.

---

## 5. Verify

```bash
# Health probe — should return {"status":"ok","redis":"up","db":"up"}
curl https://your-domain.com/health

# Market data endpoint
curl https://your-domain.com/api/v1/market

# Exchange rates only
curl https://your-domain.com/api/v1/market/exchange-rates

# Fuel prices
curl https://your-domain.com/api/v1/market/fuel-prices

# News articles
curl https://your-domain.com/api/v1/market/news
```

---

## 6. Day-2 operations

### View logs

```bash
# All services
docker compose logs -f

# Single service
docker compose logs -f fastapi
docker compose logs -f scheduler
```

### Restart a single service

```bash
docker compose restart fastapi
```

### Rebuild after a code change

```bash
docker compose up -d --build fastapi scheduler
```

### Scale the API (add more uvicorn workers via replicas)

```bash
docker compose up -d --scale fastapi=3
```

### Stop everything

```bash
docker compose down
```

### Full teardown including volumes (⚠ deletes all DB data)

```bash
docker compose down -v
```

---

## 7. Redis cache management

The FastAPI service caches every read response in Redis for `CACHE_TTL_SECONDS`
(default 30 s). To manually flush the cache:

```bash
docker compose exec redis redis-cli FLUSHDB
```

To inspect what's currently cached:

```bash
docker compose exec redis redis-cli KEYS '*'
```

---

## 8. Database backups

```bash
# Dump
docker compose exec postgres \
  pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T postgres \
  psql -U $POSTGRES_USER $POSTGRES_DB < backup_20260930.sql
```

---

## 9. TLS certificate renewal (Let's Encrypt)

Certificates expire after 90 days. Renew with:

```bash
# Stop nginx to free port 80
docker compose stop nginx

# Renew
sudo certbot renew

# Restart nginx
docker compose start nginx
```

Add this as a monthly cron job:

```cron
0 3 1 * * /usr/bin/certbot renew --pre-hook "docker compose -f /path/to/scraper/docker-compose.yml stop nginx" --post-hook "docker compose -f /path/to/scraper/docker-compose.yml start nginx"
```

---

## 10. Environment variable reference

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_DB` | `postgres` | Database name |
| `POSTGRES_USER` | `postgres` | Database user |
| `POSTGRES_PASSWORD` | — | **Required.** Database password |
| `DATABASE_URL` | built from above | Full DSN (overrides individual vars) |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |
| `CACHE_TTL_SECONDS` | `30` | How long API responses are cached |
| `FRONTEND_URL` | `*` | Allowed CORS origin(s), comma-separated |
| `SCRAPER_MIN_INTERVAL` | `30` | Minimum seconds between scrape cycles |
| `SCRAPER_MAX_INTERVAL` | `60` | Maximum seconds between scrape cycles |

---

## 11. Project structure (final)

```
scraper/
├── main.py                  # FastAPI app (Redis-cached endpoints)
├── scheduler.py             # Scraper daemon (threaded polling loop)
│
├── scraper_manager/         # Scraper package
│   ├── __init__.py
│   ├── base.py              # Shared DB config, retry decorator, logging
│   ├── energy.py            # Exchange rates, electricity news, fuel prices
│   ├── metals.py            # Gold prices (allira-sy.com)
│   ├── news.py              # Ministry of Energy articles API
│   └── cb.py                # Central Bank of Syria scraper
│
├── nginx/
│   ├── nginx.conf           # Reverse proxy config
│   └── certs/               # TLS certificates (not committed)
│       ├── fullchain.pem
│       └── privkey.pem
│
├── Dockerfile.api           # Image for FastAPI service
├── Dockerfile.scheduler     # Image for scheduler service
├── docker-compose.yml       # Full stack definition
├── requirements.txt         # Pinned Python dependencies
├── .env.example             # Environment variable template
├── .env                     # Your local secrets (never commit)
└── DEPLOYMENT.md            # This file
```
