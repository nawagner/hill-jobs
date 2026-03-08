# Leg Branch Jobs Design

**Date:** March 8, 2026

**Goal:** Build a public web app that aggregates legislative-branch job postings into one searchable destination, with filters for keyword, source organization, role category, and posting freshness. The first release should automatically ingest jobs from Senate listings, House CAO, U.S. Capitol Police, Architect of the Capitol, Library of Congress, and a forwarded House bulletin email.

## Confirmed Product Constraints

- Public web app
- Backend hosted on Railway
- Frontend hosted on Cloudflare Workers
- Postgres as the primary database
- Automated source ingestion from day one
- Custom role taxonomy for search:
  - `policy`
  - `communications`
  - `legal`
  - `operations`
  - `technology`
  - `security`
- Local job detail pages with outbound links to original postings
- Daily refresh cadence
- No admin UI in v1
- Closed jobs stay in the database but are hidden from default public search
- House of Representatives bulletin arrives by forwarded email and should be parsed automatically

## Source Patterns Verified On March 8, 2026

- Senate employer directory: `careers.employment.senate.gov` is a Web Scribble job board. It exposes an employer directory, per-office job listings, and public detail pages with titles, snippets, posting dates, and job detail URLs.
- House CAO and U.S. Capitol Police: `*.csodfed.com` uses the Cornerstone/CSOD-fed ATS pattern with a search/listing page and per-requisition detail pages. The CAO listing currently exposes job title, location, post date, requisition ID, salary range, and closing date on the detail page.
- The example Sergeant at Arms link also uses the same CSOD-fed requisition pattern, which supports a reusable adapter family for similar sites.
- Architect of the Capitol: the public careers page directs candidates to USAJobs. USAJobs offers a documented Search API, but it requires API registration and an API key.
- Library of Congress: `loc.gov/careers/` publishes current openings in structured public pages with links to per-job detail pages under `loc.gov/item/careers/...`.

## Recommended Architecture

Use one backend system of record on Railway and one public frontend on Cloudflare.

Railway responsibilities:

- Run scheduled ingestion jobs once per day
- Normalize data from all upstream sources into one canonical schema
- Assign `role_kind` using deterministic rules
- Expose public search and detail endpoints
- Persist jobs, sync metadata, raw payloads, and sync runs in Postgres

Cloudflare responsibilities:

- Serve the public web UI
- Call the Railway API for search and detail data
- Host a small inbound email worker for the forwarded House bulletin and forward parsed records to Railway using a signed webhook

This keeps scraping, scheduler behavior, secrets, source retries, and database writes in one place. The frontend remains thin and fast.

## Backend Technology Choice

Use Python for the backend.

Why Python fits this project:

- The hardest part is source ingestion and normalization, not frontend/backend type sharing.
- HTML parsing, feed normalization, fixture-driven testing, and one-off extraction work are ergonomically strong in Python.
- Railway runs FastAPI services cleanly, and Python Playwright is available if a dynamic source eventually needs browser rendering.

Recommended backend stack:

- FastAPI for HTTP routes
- SQLAlchemy 2.x for ORM and query building
- Alembic for migrations
- Pydantic for request/response and ingest validation
- `httpx` for outbound HTTP
- `beautifulsoup4` plus `lxml` for parsing
- `pytest` for backend tests
- Python Playwright only as a source-specific fallback

## Canonical Data Model

The core table is `jobs`.

Recommended fields:

- `id`
- `slug`
- `source_system`
- `source_organization`
- `source_job_id`
- `source_url`
- `title`
- `description_html`
- `description_text`
- `location_text`
- `employment_type`
- `posted_at`
- `closing_at`
- `status`
- `role_kind`
- `search_document`
- `first_seen_at`
- `last_seen_at`
- `last_synced_at`
- `raw_payload`

Supporting tables:

- `source_sync_runs` to track start time, end time, source, counts, and errors
- `job_source_keys` if a source needs composite identity rules
- `ingest_events` only if audit history becomes necessary after v1

Deduplication should default to `(source_system, source_job_id)` when available. If a source does not expose a stable ID, fall back to a deterministic hash of normalized title, organization, location, and detail URL.

## Search Behavior

Public search should support:

- Full-text keyword search across `title` and `description_text`
- Filter by `role_kind`
- Filter by `source_organization`
- Filter by recency or status

Use Postgres full-text search plus trigram indexes rather than a separate search engine. That keeps infrastructure minimal and is more than sufficient for the first release.

Closed jobs remain stored in Postgres. Default public queries should only return `open` and `unknown` jobs. Closed jobs should still have detail pages and a visible status indicator.

## Categorization Strategy

Start with deterministic rules, not ML.

Classification order:

1. Title match rules
2. Description keyword rules
3. Organization-specific overrides
4. Fallback bucket

Because there is no admin UI in v1, the rules must be explicit and versioned in code. Keep the rules small, testable, and transparent. A correction should mean adding or editing a rule, not retraining anything.

## Ingestion Strategy By Source

### Senate

Scrape the employer directory and the per-employer listing pages from `careers.employment.senate.gov`. Extract each public job page and store the organization as the Senate office or committee name. Since the Senate site already exposes job pages directly, treat it as its own adapter rather than redirecting to any linked external site.

### CSOD-fed Family

Create one reusable adapter for the CSOD-fed requisition pattern and configure it per employer:

- House CAO
- U.S. Capitol Police
- Future sources like Sergeant at Arms if desired

The adapter should fetch the listing page, collect requisition URLs, then fetch each detail page and extract title, requisition ID, location, post date, closing date, salary range when present, and description.

First try plain HTTP fetch plus HTML parsing. If a source stops returning complete markup to non-browser requests, add a Python Playwright fallback only for that adapter.

### Architect of the Capitol

Use the USAJobs Search API once an API key is obtained. Query by the Architect of the Capitol organization code or organization name as supported by the API. This is better than scraping the AOC page because the public AOC page is a referral page, not the job system of record.

### Library of Congress

Scrape the public `loc.gov/careers/` listing pages and detail pages under `loc.gov/item/careers/...`. LOC already publishes useful filters and structured titles publicly, so this can likely remain a pure HTTP adapter.

### House Bulletin Email

Use a small Cloudflare email worker that receives a forwarded bulletin email, parses HTML and plain text, extracts job entries and source links, and posts normalized records into a protected Railway endpoint. Since there is no admin UI, keep the parser conservative and store raw email content for debugging.

## Status And Closure Rules

Do not immediately mark a job closed just because it disappears from one sync. Upstream sites fail transiently, pagination changes, and email bulletins can be incomplete.

Recommended rule:

- Mark as `open` when seen in a sync or when a detail page has a future closing date
- Mark as `closed` when the source explicitly indicates closure, or after the same job is absent from two consecutive successful syncs for that source
- Mark as `unknown` when the adapter could not determine a definitive status

This avoids false closures from transient scraper failures.

## API Shape

Public endpoints:

- `GET /health`
- `GET /api/jobs`
- `GET /api/jobs/{slug}`
- `GET /api/organizations`
- `GET /api/role-kinds`

Protected endpoints:

- `POST /api/internal/ingest/run`
- `POST /api/internal/ingest/house-bulletin`

Keep public responses UI-ready so the frontend does not need to reconstruct status labels or parse dates.

## Frontend Behavior

The public app should have two primary routes:

- Search page with keyword input, role category filter, source organization filter, and a simple freshness control
- Detail page with normalized job metadata, extracted description, source organization, status badge, and a clear outbound link to the original posting

The design should favor speed and readability over feature density. This is a specialized directory, not a generic mega-job-board.

## Error Handling And Observability

Add structured logs for:

- Source sync start and finish
- Number of listings fetched
- Number of jobs inserted, updated, unchanged, and closed
- Parse failures with source URL and reason
- Email parse failures with message ID when available

Expose sync metrics in Postgres first. Full observability tooling can wait.

## Testing Strategy

Testing should focus on source contracts and normalization stability.

- Unit tests for category rules
- Parser fixture tests for every source adapter
- API tests for search filters and hidden-closed-job behavior
- Frontend route tests for search and detail rendering
- One end-to-end smoke test for the full public flow once the app exists

Avoid live-network tests in CI. Save representative HTML fixtures for each source and test against them.

## Deployment Shape

- Railway service: FastAPI app and scheduled ingestion job
- Railway Postgres: canonical database
- Cloudflare Worker: public web app
- Cloudflare email worker: House bulletin ingestion

Use a monorepo with a Python backend and TypeScript frontend. `uv` for backend dependencies and `pnpm` for the frontend and email worker is the simplest fit.
