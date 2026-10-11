# Hill Jobs Project Notes

## Railway CLI

Project: `hill-jobs`, Environment: `production`

### Services
- **beneficial-beauty** — FastAPI backend (API service)
  - Domain: `https://beneficial-beauty-production.up.railway.app`
- **Postgres** — Database
- **ingest-cron** — Daily ingestion of all sources (`apps/api/scripts/cron_ingest.py`)
  - Built from the same `apps/api/Dockerfile` as the API; the service variable `INSTALL_CHROMIUM=1` adds Chromium for CSOD
  - Settings (Railway dashboard): root dir `/apps/api`, start command `uv run --no-sync python scripts/cron_ingest.py`, cron `0 10 * * *` (UTC), restart policy `NEVER`
  - The repo-root `railway.toml` overrides dashboard build settings for every service, so don't point a service at a different Dockerfile from the dashboard
  - Variables reference `beneficial-beauty` (`DATABASE_URL`, `USAJOBS_API_KEY`, `OPENROUTER_API_KEY`); HVAPS also needs `GMAIL_APP_PASSWORD` (and `GMAIL_ADDRESS` if not the default)
  - Exits non-zero if a source errors or unexpectedly returns 0 jobs, so check its deployment status/logs when data looks stale

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
- `POST /api/internal/ingest/hvaps?pdf_url=<url>` — HVAPS PDF bulletin ingest (manual fallback; HVAPS is normally picked up automatically from Gmail)

## Triggering Ingestion

Ingestion runs daily on the `ingest-cron` Railway service. Don't move it back to a GitHub Actions `schedule:`: GitHub disables scheduled workflows after 60 days without repo activity, which silently froze the site from August to October 2026.

To trigger the server-side (non-browser) sources manually:
```bash
# Get the token (table output truncates long values, always use --json)
TOKEN=$(railway variables --service beneficial-beauty --json 2>&1 | python3 -c "import sys,json; print(json.load(sys.stdin)['INTERNAL_INGEST_TOKEN'])")
curl -X POST "https://beneficial-beauty-production.up.railway.app/api/internal/ingest/run" -H "x-internal-token: $TOKEN"

# Manual HVAPS fallback (only needed if the email adapter missed a bulletin)
curl -X POST "https://beneficial-beauty-production.up.railway.app/api/internal/ingest/hvaps?pdf_url=<PASTE_PDF_URL_HERE>" -H "x-internal-token: $TOKEN"
```

## Ingestion Sources

| Adapter | Source System | Method | Runs On |
|---|---|---|---|
| `HouseDemsResumebankAdapter` | `house-dems-resumebank` | REST API (domewatch.us) | Railway cron |
| `SenateAdapter` | `senate-webscribble` | REST API | Railway cron |
| `LocAdapter` | `loc-careers` | Web scraping | Railway cron |
| `UsajobsAdapter` (AOC) | `aoc-usajobs` | USAJobs API (needs key) | Railway cron |
| `UsajobsAdapter` (GAO) | `gao-usajobs` | USAJobs API (needs key) | Railway cron |
| `UsajobsAdapter` (GPO) | `gpo-usajobs` | USAJobs API (needs key) | Railway cron |
| `CboBizmerlinAdapter` | `cbo-bizmerlin` | REST API (cbo.clayhr.com, formerly BizMerlin) | Railway cron |
| `CsodAdapter` | `csod-house-cao`, `csod-house-clerk`, `csod-house-saa`, `csod-house-green-gold`, `csod-uscp` | Playwright (Chromium) | Railway cron |
| `HvapsEmailAdapter` | `house-hvaps` | Gmail IMAP → PDF parsing | Railway cron |
| HVAPS endpoint | `house-hvaps` | PDF parsing (manual URL fallback) | Railway API |

## Changelog

Update `CHANGELOG.md` at the repo root when making major changes (new adapters, new features, breaking changes, significant bug fixes). Keep entries concise.

## Running Tests

```bash
cd apps/api && uv run pytest tests/ -v
```
