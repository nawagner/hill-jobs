# Hill Jobs Project Notes

## Railway CLI

Project: `hill-jobs`, Environment: `production`

### Services
- **beneficial-beauty** — FastAPI backend (API service)
  - Domain: `https://beneficial-beauty-production.up.railway.app`
- **Postgres** — Database

### Useful commands
```bash
railway status                          # Show linked project/env
railway service status --all            # List all services and their status
railway domain --service beneficial-beauty  # Show/manage domains for the API
railway logs --service beneficial-beauty    # View API logs
railway variable --service beneficial-beauty  # Manage env vars
```

### Direct database access

For ad-hoc queries, connect directly instead of going through the Railway CLI:
```bash
# From apps/api/, using psycopg (no psycopg2):
# Get the DATABASE_URL from Railway (never hardcode credentials):
DATABASE_URL=$(railway variables --service Postgres --json 2>&1 | python3 -c "import sys,json; print(json.load(sys.stdin)['DATABASE_URL'])") \
  uv run python -c "
from sqlalchemy import create_engine, text
import os
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    for r in conn.execute(text('SELECT id, title FROM jobs LIMIT 5')).fetchall():
        print(r)
"
```

### Notes
- `railway service` requires a service name in non-interactive mode
- Use `--service <name>` flag or `--all` when no service is linked
- `railway domain` without args on an unlinked service errors; pass `--service`

## Monorepo Structure

- `apps/api/` — Python FastAPI backend (deployed to Railway)
- `apps/web/` — Frontend (to be deployed to Cloudflare Workers)
- `apps/email-worker/` — Cloudflare email worker for House bulletin parsing

## Browser Scraping

For JavaScript-rendered career sites (e.g., CSOD/csodfed.com), use the `agent-browser` CLI tool instead of Playwright. It's installed globally via npm and provides headless browser automation via simple CLI commands (`open`, `wait`, `eval`, `close`).

## API Endpoints

Public:
- `GET /api/jobs?q=&role_kind=&organization=&status=&posted_since_days=&page=`
- `GET /api/jobs/{slug}`
- `GET /api/organizations`
- `GET /api/role-kinds`

Protected (requires `x-internal-token` header):
- `POST /api/internal/ingest/run`
- `POST /api/internal/ingest/hvaps?pdf_url=<url>` — HVAPS PDF bulletin ingest

## Triggering Ingestion

To trigger ingestion manually:
```bash
# Get the token (table output truncates long values, always use --json)
TOKEN=$(railway variables --service beneficial-beauty --json 2>&1 | python3 -c "import sys,json; print(json.load(sys.stdin)['INTERNAL_INGEST_TOKEN'])")
curl -X POST "https://beneficial-beauty-production.up.railway.app/api/internal/ingest/run" -H "x-internal-token: $TOKEN"

# Ingest HVAPS PDF (paste the PDF URL from the weekly email)
curl -X POST "https://beneficial-beauty-production.up.railway.app/api/internal/ingest/hvaps?pdf_url=<PASTE_PDF_URL_HERE>" -H "x-internal-token: $TOKEN"
```

## Ingestion Sources

| Adapter | Source System | Method | Runs On |
|---|---|---|---|
| `HouseDemsResumebankAdapter` | `house-dems-resumebank` | REST API (domewatch.us) | Railway |
| `SenateAdapter` | `senate-webscribble` | REST API | Railway |
| `LocAdapter` | `loc-careers` | Web scraping | Railway |
| `UsajobsAdapter` (AOC) | `aoc-usajobs` | USAJobs API (needs key) | Railway |
| `UsajobsAdapter` (GAO) | `gao-usajobs` | USAJobs API (needs key) | Railway |
| `UsajobsAdapter` (GPO) | `gpo-usajobs` | USAJobs API (needs key) | Railway |
| `CboBizmerlinAdapter` | `cbo-bizmerlin` | REST API (bizmerlin.net) | Railway |
| `CsodAdapter` | `csod-house-cao`, `csod-uscp` | agent-browser | Local only |
| HVAPS endpoint | `house-hvaps` | PDF parsing (manual URL trigger) | Railway |

## Changelog

Update `CHANGELOG.md` at the repo root when making major changes (new adapters, new features, breaking changes, significant bug fixes). Keep entries concise.

## Running Tests

```bash
cd apps/api && uv run pytest tests/ -v
```
