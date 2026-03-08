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
