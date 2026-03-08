# Leg Branch Jobs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a public legislative-branch jobs web app that ingests jobs from Senate, House CAO, U.S. Capitol Police, Architect of the Capitol, Library of Congress, and a forwarded House bulletin, then exposes searchable listings and local detail pages.

**Architecture:** Use a Python monorepo with a Railway-hosted FastAPI backend and Postgres database, plus a Cloudflare Worker-hosted React frontend. Keep all ingestion, normalization, and search logic in the backend, while the frontend consumes a small public API and renders search/detail pages. Use a dedicated Cloudflare email worker to parse House bulletin forwards and submit them to a protected backend endpoint.

**Tech Stack:** Python 3.12, `uv`, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, PostgreSQL, `httpx`, `beautifulsoup4`, `lxml`, `pytest`, Python Playwright only as an adapter fallback, React, React Router, Vite, Cloudflare Workers, Wrangler.

## Proposed Repository Structure

```text
.
├── Makefile
├── .gitignore
├── README.md
├── apps
│   ├── api
│   │   ├── pyproject.toml
│   │   ├── uv.lock
│   │   ├── alembic.ini
│   │   ├── app
│   │   │   ├── main.py
│   │   │   ├── config.py
│   │   │   ├── db
│   │   │   │   ├── base.py
│   │   │   │   ├── session.py
│   │   │   │   ├── models.py
│   │   │   │   └── migrations
│   │   │   ├── api
│   │   │   │   └── routes
│   │   │   │       ├── health.py
│   │   │   │       ├── jobs.py
│   │   │   │       └── internal_ingest.py
│   │   │   ├── schemas
│   │   │   │   ├── jobs.py
│   │   │   │   └── ingest.py
│   │   │   ├── search
│   │   │   │   ├── query_jobs.py
│   │   │   │   └── slugs.py
│   │   │   ├── categorization
│   │   │   │   ├── role_kinds.py
│   │   │   │   └── classify_job.py
│   │   │   ├── ingest
│   │   │   │   ├── run_all.py
│   │   │   │   ├── source_registry.py
│   │   │   │   ├── normalize_job.py
│   │   │   │   ├── upsert_jobs.py
│   │   │   │   ├── mark_missing_jobs.py
│   │   │   │   └── adapters
│   │   │   │       ├── senate.py
│   │   │   │       ├── csod.py
│   │   │   │       ├── aoc_usajobs.py
│   │   │   │       ├── loc.py
│   │   │   │       └── house_bulletin.py
│   │   │   └── lib
│   │   │       ├── fetch_html.py
│   │   │       ├── logger.py
│   │   │       └── clock.py
│   │   └── tests
│   │       ├── categorization
│   │       ├── ingest
│   │       ├── routes
│   │       └── fixtures
│   ├── web
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   ├── vite.config.ts
│   │   ├── wrangler.jsonc
│   │   └── src
│   │       ├── main.tsx
│   │       ├── app.tsx
│   │       ├── styles.css
│   │       ├── lib
│   │       │   └── api.ts
│   │       ├── routes
│   │       │   ├── home.tsx
│   │       │   └── job-detail.tsx
│   │       └── components
│   │           ├── search-form.tsx
│   │           ├── filters.tsx
│   │           ├── job-card.tsx
│   │           └── status-badge.tsx
│   └── email-worker
│       ├── package.json
│       ├── tsconfig.json
│       ├── wrangler.jsonc
│       └── src
│           ├── index.ts
│           └── parse-house-bulletin.ts
└── docs
    └── runbooks
```

### Task 1: Initialize The Mixed Python And Frontend Workspace

**Files:**
- Create: `Makefile`
- Create: `.gitignore`
- Create: `README.md`
- Create: `apps/api/pyproject.toml`
- Create: `apps/web/package.json`
- Create: `apps/email-worker/package.json`

**Step 1: Write the failing validation**

Create a `Makefile` that assumes all three apps are wired:

```make
api-test:
	cd apps/api && uv run pytest

web-test:
	cd apps/web && pnpm test

email-test:
	cd apps/email-worker && pnpm test

test: api-test web-test email-test
```

**Step 2: Run validation to verify it fails**

Run: `make test`
Expected: FAIL because the apps and dependency manifests do not exist yet.

**Step 3: Write minimal workspace files**

Create a Python backend project in `apps/api/pyproject.toml`:

```toml
[project]
name = "leg-branch-jobs-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi",
  "uvicorn[standard]",
  "sqlalchemy",
  "alembic",
  "psycopg[binary]",
  "pydantic",
  "pydantic-settings",
  "httpx",
  "beautifulsoup4",
  "lxml",
]

[dependency-groups]
dev = [
  "pytest",
  "pytest-asyncio",
  "httpx",
  "respx",
]
```

**Step 4: Run validation to verify it passes**

Run: `cd apps/api && uv sync`
Expected: PASS with `uv.lock` created.

**Step 5: Commit**

```bash
git add Makefile .gitignore README.md apps/api/pyproject.toml apps/web/package.json apps/email-worker/package.json
git commit -m "chore: initialize project workspace"
```

### Task 2: Add Shared Backend Domain Models

**Files:**
- Create: `apps/api/app/categorization/role_kinds.py`
- Create: `apps/api/app/schemas/jobs.py`
- Create: `apps/api/tests/categorization/test_role_kinds.py`

**Step 1: Write the failing test**

```python
from app.categorization.role_kinds import ROLE_KINDS


def test_role_kinds_match_product_taxonomy():
    assert ROLE_KINDS == (
        "policy",
        "communications",
        "legal",
        "operations",
        "technology",
        "security",
    )
```

**Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/categorization/test_role_kinds.py -q`
Expected: FAIL because the module does not exist.

**Step 3: Write minimal implementation**

```python
ROLE_KINDS = (
    "policy",
    "communications",
    "legal",
    "operations",
    "technology",
    "security",
)
```

Create Pydantic response models for `JobListItem`, `JobDetail`, and `JobSearchResponse`.

**Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/categorization/test_role_kinds.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/api/app/categorization/role_kinds.py apps/api/app/schemas/jobs.py apps/api/tests/categorization/test_role_kinds.py
git commit -m "feat: add backend domain schemas"
```

### Task 3: Stand Up FastAPI And The Health Route

**Files:**
- Create: `apps/api/app/main.py`
- Create: `apps/api/app/api/routes/health.py`
- Create: `apps/api/tests/routes/test_health.py`

**Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient
from app.main import app


def test_health_returns_ok():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
```

**Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/routes/test_health.py -q`
Expected: FAIL because the app does not exist.

**Step 3: Write minimal implementation**

```python
from fastapi import FastAPI
from app.api.routes.health import router as health_router

app = FastAPI()
app.include_router(health_router)
```

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True}
```

**Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/routes/test_health.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/api/app/main.py apps/api/app/api/routes/health.py apps/api/tests/routes/test_health.py
git commit -m "feat: scaffold fastapi service"
```

### Task 4: Add Postgres Models And Alembic Migration

**Files:**
- Create: `apps/api/app/db/base.py`
- Create: `apps/api/app/db/session.py`
- Create: `apps/api/app/db/models.py`
- Create: `apps/api/alembic.ini`
- Create: `apps/api/app/db/migrations/versions/0001_initial.py`
- Create: `apps/api/tests/routes/test_schema.py`

**Step 1: Write the failing test**

Write a test that asserts the metadata contains:

- `jobs`
- `source_sync_runs`
- a unique constraint for source identity

**Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/routes/test_schema.py -q`
Expected: FAIL because the ORM models do not exist.

**Step 3: Write minimal implementation**

`jobs` should include:

```python
slug = mapped_column(String, unique=True, nullable=False)
source_system = mapped_column(String, nullable=False)
source_organization = mapped_column(String, nullable=False)
source_job_id = mapped_column(String)
source_url = mapped_column(String, nullable=False)
title = mapped_column(String, nullable=False)
description_html = mapped_column(Text, nullable=False)
description_text = mapped_column(Text, nullable=False)
status = mapped_column(String, nullable=False)
role_kind = mapped_column(String, nullable=False)
raw_payload = mapped_column(JSON, nullable=False)
```

Add a migration with a GIN index for `search_document`.

**Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/routes/test_schema.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/api/app/db apps/api/alembic.ini apps/api/tests/routes/test_schema.py
git commit -m "feat: add database schema"
```

### Task 5: Implement Deterministic Role Classification

**Files:**
- Create: `apps/api/app/categorization/classify_job.py`
- Create: `apps/api/tests/categorization/test_classify_job.py`

**Step 1: Write the failing test**

```python
from app.categorization.classify_job import classify_job


def test_communications_title_maps_correctly():
    assert classify_job(
        title="Communications Director",
        description_text="",
        source_organization="House CAO",
    ) == "communications"


def test_security_title_maps_correctly():
    assert classify_job(
        title="Cybersecurity Senior Specialist",
        description_text="",
        source_organization="Senate Sergeant at Arms",
    ) == "security"
```

**Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/categorization/test_classify_job.py -q`
Expected: FAIL because the classifier does not exist.

**Step 3: Write minimal implementation**

```python
TITLE_RULES = [
    ("communications", [r"communications?", r"press", r"writer", r"editor"]),
    ("legal", [r"counsel", r"attorney", r"\blaw\b"]),
    ("policy", [r"policy", r"legislative", r"research specialist"]),
    ("technology", [r"engineer", r"developer", r"systems?", r"product owner"]),
    ("security", [r"security", r"cyber", r"police", r"threat"]),
]
```

Add description keyword fallback and default to `operations`.

**Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/categorization/test_classify_job.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/api/app/categorization/classify_job.py apps/api/tests/categorization/test_classify_job.py
git commit -m "feat: add job role classifier"
```

### Task 6: Build Public Search And Detail Routes

**Files:**
- Create: `apps/api/app/api/routes/jobs.py`
- Create: `apps/api/app/search/query_jobs.py`
- Create: `apps/api/app/search/slugs.py`
- Create: `apps/api/tests/routes/test_jobs.py`

**Step 1: Write the failing test**

Cover:

- default list excludes closed jobs
- keyword filter narrows results
- organization filter narrows results
- `GET /api/jobs/{slug}` returns a detail record

**Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/routes/test_jobs.py -q`
Expected: FAIL because the route and query layer do not exist.

**Step 3: Write minimal implementation**

Create:

- `GET /api/jobs`
- `GET /api/jobs/{slug}`
- `GET /api/organizations`
- `GET /api/role-kinds`

Supported query params:

- `q`
- `role_kind`
- `organization`
- `status`
- `posted_since_days`
- `page`

**Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/routes/test_jobs.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/api/app/api/routes/jobs.py apps/api/app/search apps/api/tests/routes/test_jobs.py
git commit -m "feat: add public jobs api"
```

### Task 7: Add Ingestion Core And Upsert Logic

**Files:**
- Create: `apps/api/app/ingest/source_registry.py`
- Create: `apps/api/app/ingest/normalize_job.py`
- Create: `apps/api/app/ingest/upsert_jobs.py`
- Create: `apps/api/app/ingest/mark_missing_jobs.py`
- Create: `apps/api/app/ingest/run_all.py`
- Create: `apps/api/tests/ingest/test_upsert_jobs.py`

**Step 1: Write the failing test**

Test that:

- a new job inserts
- a seen-again job updates `last_seen_at`
- a missing job is not closed until absent for two successful syncs

**Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/ingest/test_upsert_jobs.py -q`
Expected: FAIL because the ingest services do not exist.

**Step 3: Write minimal implementation**

Normalized adapter shape:

```python
class SourceJob(BaseModel):
    source_system: str
    source_organization: str
    source_job_id: str | None = None
    source_url: str
    title: str
    description_html: str
    description_text: str
    location_text: str | None = None
    employment_type: str | None = None
    posted_at: datetime | None = None
    closing_at: datetime | None = None
    raw_payload: dict
```

The upsert layer should:

- create slug
- classify role kind
- compute `search_document`
- insert or update the row
- track sync counts
- mark items closed only after two missed successful syncs

**Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/ingest/test_upsert_jobs.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/api/app/ingest apps/api/tests/ingest/test_upsert_jobs.py
git commit -m "feat: add ingestion pipeline core"
```

### Task 8: Implement Senate And LOC Adapters

**Files:**
- Create: `apps/api/app/ingest/adapters/senate.py`
- Create: `apps/api/app/ingest/adapters/loc.py`
- Create: `apps/api/tests/fixtures/senate/`
- Create: `apps/api/tests/fixtures/loc/`
- Create: `apps/api/tests/ingest/test_senate.py`
- Create: `apps/api/tests/ingest/test_loc.py`

**Step 1: Write the failing tests**

Use saved fixtures from:

- Senate employer directory page
- Senate employer detail page
- one Senate job detail page
- LOC careers listing page
- one LOC job detail page

Assert:

- correct listing count extraction
- stable source IDs
- correct dates
- correct organization names

**Step 2: Run tests to verify they fail**

Run: `cd apps/api && uv run pytest tests/ingest/test_senate.py tests/ingest/test_loc.py -q`
Expected: FAIL because the adapters do not exist.

**Step 3: Write minimal implementation**

Senate adapter responsibilities:

- crawl employer directory pages
- collect employer URLs
- parse employer job cards
- fetch each job page
- emit `source_system="senate-webscribble"`

LOC adapter responsibilities:

- fetch `https://www.loc.gov/careers/?all=true`
- collect job item URLs
- parse each detail page
- emit `source_system="loc-careers"`

**Step 4: Run tests to verify they pass**

Run: `cd apps/api && uv run pytest tests/ingest/test_senate.py tests/ingest/test_loc.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/api/app/ingest/adapters/senate.py apps/api/app/ingest/adapters/loc.py apps/api/tests/fixtures apps/api/tests/ingest
git commit -m "feat: add senate and loc adapters"
```

### Task 9: Implement The Reusable CSOD Adapter

**Files:**
- Create: `apps/api/app/ingest/adapters/csod.py`
- Create: `apps/api/tests/fixtures/csod/house-listing.html`
- Create: `apps/api/tests/fixtures/csod/house-detail.html`
- Create: `apps/api/tests/fixtures/csod/uscp-listing.html`
- Create: `apps/api/tests/ingest/test_csod.py`

**Step 1: Write the failing test**

Assert that the adapter:

- parses requisition URLs
- extracts requisition IDs from detail pages
- parses post date and closing date
- keeps source organization configurable

**Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/ingest/test_csod.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class CsodSourceConfig:
    source_system: str
    source_organization: str
    home_url: str
    company_code: str
```

Implement:

- `fetch_listing(config)`
- `extract_requisition_urls(html)`
- `fetch_detail(url)`
- `parse_detail(html, url, organization)`

Start with plain HTTP fetch plus BeautifulSoup. Add a Python Playwright fallback hook but do not wire it until a real source requires it.

**Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/ingest/test_csod.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/api/app/ingest/adapters/csod.py apps/api/tests/fixtures/csod apps/api/tests/ingest/test_csod.py
git commit -m "feat: add reusable csod adapter"
```

### Task 10: Add The AOC USAJobs Adapter

**Files:**
- Create: `apps/api/app/ingest/adapters/aoc_usajobs.py`
- Create: `apps/api/tests/fixtures/usajobs/search-response.json`
- Create: `apps/api/tests/ingest/test_aoc_usajobs.py`
- Modify: `apps/api/app/config.py`

**Step 1: Write the failing test**

Use a saved USAJobs Search API response fixture and assert:

- only AOC postings are emitted
- title, organization, posting date, closing date, and apply URL are parsed
- missing API key is handled as a configuration error

**Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/ingest/test_aoc_usajobs.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

```python
class Settings(BaseSettings):
    database_url: str
    internal_ingest_token: str
    usajobs_api_key: str | None = None
    usajobs_user_agent_email: str | None = None
```

Implement the adapter to call `https://data.usajobs.gov/api/Search` with the required headers only when the API key is configured. If the key is missing, log and skip the source instead of crashing the full sync.

**Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/ingest/test_aoc_usajobs.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/api/app/ingest/adapters/aoc_usajobs.py apps/api/app/config.py apps/api/tests/fixtures/usajobs apps/api/tests/ingest/test_aoc_usajobs.py
git commit -m "feat: add aoc usajobs adapter"
```

### Task 11: Add House Bulletin Email Ingestion

**Files:**
- Create: `apps/email-worker/src/index.ts`
- Create: `apps/email-worker/src/parse-house-bulletin.ts`
- Create: `apps/email-worker/wrangler.jsonc`
- Create: `apps/email-worker/tests/parse-house-bulletin.test.ts`
- Modify: `apps/api/app/api/routes/internal_ingest.py`
- Create: `apps/api/app/schemas/ingest.py`
- Create: `apps/api/tests/routes/test_internal_ingest.py`

**Step 1: Write the failing test**

Test that a sample forwarded bulletin email:

- produces structured job entries
- preserves source URLs when present
- rejects unsigned webhook posts to the backend

**Step 2: Run test to verify it fails**

Run: `cd apps/email-worker && pnpm test`
Expected: FAIL because the parser and endpoint do not exist.

Run: `cd apps/api && uv run pytest tests/routes/test_internal_ingest.py -q`
Expected: FAIL because the protected route does not exist.

**Step 3: Write minimal implementation**

Email worker shape:

```ts
export default {
  async email(message, env) {
    const parsed = await parseHouseBulletin(message);
    await fetch(`${env.API_URL}/api/internal/ingest/house-bulletin`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-internal-token": env.INTERNAL_INGEST_TOKEN,
      },
      body: JSON.stringify(parsed),
    });
  },
};
```

Backend route should:

- require `x-internal-token`
- validate payload with Pydantic
- upsert bulletin jobs with `source_system="house-bulletin"`

**Step 4: Run test to verify it passes**

Run: `cd apps/email-worker && pnpm test`
Expected: PASS.

Run: `cd apps/api && uv run pytest tests/routes/test_internal_ingest.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/email-worker apps/api/app/api/routes/internal_ingest.py apps/api/app/schemas/ingest.py apps/api/tests/routes/test_internal_ingest.py
git commit -m "feat: add house bulletin ingestion"
```

### Task 12: Build The Cloudflare Frontend

**Files:**
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/app.tsx`
- Create: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/routes/home.tsx`
- Create: `apps/web/src/routes/job-detail.tsx`
- Create: `apps/web/src/components/search-form.tsx`
- Create: `apps/web/src/components/filters.tsx`
- Create: `apps/web/src/components/job-card.tsx`
- Create: `apps/web/src/components/status-badge.tsx`
- Create: `apps/web/src/styles.css`
- Create: `apps/web/src/routes/home.test.tsx`
- Create: `apps/web/src/routes/job-detail.test.tsx`

**Step 1: Write the failing tests**

Cover:

- home page renders search controls
- search results render organization and role kind
- detail page renders local content and outbound source link
- closed jobs show a visible closed status badge

**Step 2: Run tests to verify they fail**

Run: `cd apps/web && pnpm test`
Expected: FAIL because the frontend does not exist.

**Step 3: Write minimal implementation**

Home route behavior:

- load query params
- fetch `/api/jobs`
- render filters and cards

Detail route behavior:

- fetch `/api/jobs/{slug}`
- render normalized metadata
- render description HTML
- render `Apply at source` link

Keep the visual design simple, fast, and readable. Do not add saved jobs, auth, or personalization in v1.

**Step 4: Run tests to verify they pass**

Run: `cd apps/web && pnpm test`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/web
git commit -m "feat: add public jobs frontend"
```

### Task 13: Wire Scheduled Syncs And Source Registry

**Files:**
- Modify: `apps/api/app/ingest/source_registry.py`
- Modify: `apps/api/app/ingest/run_all.py`
- Modify: `apps/api/app/api/routes/internal_ingest.py`
- Create: `apps/api/tests/ingest/test_run_all.py`
- Create: `docs/runbooks/ingestion.md`

**Step 1: Write the failing test**

Assert that `run_all_sources()`:

- executes each configured source
- records a sync run
- keeps one source failure from aborting the rest

**Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/ingest/test_run_all.py -q`
Expected: FAIL because orchestration is incomplete.

**Step 3: Write minimal implementation**

The registry should include:

- `senate-webscribble`
- `csod-house-cao`
- `csod-uscp`
- `aoc-usajobs`
- `loc-careers`

Expose an internal route for Railway cron or external scheduler:

- `POST /api/internal/ingest/run`

The handler should validate the token, call `run_all_sources()`, and return per-source counts.

**Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest tests/ingest/test_run_all.py -q`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/api/app/ingest/source_registry.py apps/api/app/ingest/run_all.py apps/api/app/api/routes/internal_ingest.py apps/api/tests/ingest/test_run_all.py docs/runbooks/ingestion.md
git commit -m "feat: add scheduled ingestion orchestration"
```

### Task 14: Add End-To-End Verification And Deployment Docs

**Files:**
- Create: `apps/api/tests/e2e/test_public_flow.py`
- Create: `docs/runbooks/deploy.md`
- Modify: `README.md`

**Step 1: Write the failing test**

Create one smoke test that:

- seeds a small fixture dataset
- calls the search API with `technology`
- fetches a job detail record
- verifies the outbound source URL exists

**Step 2: Run test to verify it fails**

Run: `cd apps/api && uv run pytest tests/e2e/test_public_flow.py -q`
Expected: FAIL because final integration wiring is not complete.

**Step 3: Write minimal implementation**

Document:

- Railway environment variables
- Railway cron trigger
- Cloudflare Worker deploy command
- Cloudflare email worker setup
- USAJobs API key registration step

Recommended environment variables:

```bash
DATABASE_URL=
INTERNAL_INGEST_TOKEN=
USAJOBS_API_KEY=
USAJOBS_USER_AGENT_EMAIL=
PUBLIC_API_BASE_URL=
```

**Step 4: Run test to verify it passes**

Run: `cd apps/api && uv run pytest`
Expected: PASS for backend unit and integration coverage.

Run: `cd apps/web && pnpm test`
Expected: PASS for frontend coverage.

Run: `cd apps/email-worker && pnpm test`
Expected: PASS for email worker coverage.

**Step 5: Commit**

```bash
git add apps/api/tests/e2e/test_public_flow.py docs/runbooks/deploy.md README.md
git commit -m "docs: add deployment and verification guides"
```

## Verification Checklist

Run these before claiming the build is ready:

```bash
cd apps/api && uv sync && uv run pytest
cd apps/web && pnpm install && pnpm test
cd apps/email-worker && pnpm install && pnpm test
```

Then run one manual smoke pass:

1. Seed a few jobs from fixtures.
2. Open the frontend locally.
3. Search for `engineer`.
4. Filter to `technology`.
5. Open a detail page.
6. Confirm the source link points to the original posting.
7. Confirm a closed job is hidden from default results.

## External Dependencies

- Railway Postgres
- Railway service for FastAPI and scheduled ingestion
- Cloudflare Worker for the public frontend
- Cloudflare email worker for inbound House bulletin processing
- USAJobs API key for AOC ingestion

## Risks To Handle Early

- CSOD-fed markup can change and may eventually require browser rendering for some sources.
- The House bulletin email format may be inconsistent across forwards, so raw-message retention matters.
- USAJobs access is blocked until API registration is approved.
- Some sources may omit reliable closing dates, so absence-based closure logic must be conservative.
