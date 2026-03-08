# Leg Branch Jobs

Public legislative-branch jobs app with a FastAPI backend, Cloudflare-hosted frontend, and email ingestion worker.

## Apps

- `apps/api`: FastAPI API, ingestion pipeline, and search backend
- `apps/web`: public web frontend
- `apps/email-worker`: Cloudflare email worker for House bulletin ingestion

## Data Sources

| Source | Adapter | Auth | Notes |
|---|---|---|---|
| U.S. Senate careers | `senate-webscribble` | None | Paginated API at careers.employment.senate.gov |
| House CAO (CSOD) | `csod-house-cao` | None | Browser-rendered SPA via agent-browser |
| U.S. Capitol Police (CSOD) | `csod-uscp` | None | Browser-rendered SPA via agent-browser |
| Library of Congress | `loc-careers` | None | HTML scraping of loc.gov/careers |
| Architect of the Capitol | `aoc-usajobs` | USAJobs API key | USAJobs API (conditional on config) |
| House Democrats Resume Bank | `house-dems-resumebank` | None | JSON API at resumebank.domewatch.us (Dem offices only) |
