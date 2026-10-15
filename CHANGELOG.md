# Changelog

## 2026-10-15

- Redraw the hero's Capitol dome from an 1897 Library of Congress photo; the top looked like a candle
  - The Statue of Freedom is a robed figure with a shield and crested helmet, standing on a globe; her glint now fades out instead of leaving a flame-like glow
  - Taller lantern with six columns and a bell-shaped cap; lower dome shell with a row of windows; shorter drum
  - Columns and windows crowd toward the edges of the dome and its rings curve, as seen from the ground

## 2026-10-14

- Add Capitol motion graphics to the site
  - Home page hero: a gold line drawing of the Capitol's west front draws itself on the first visit (about 3 seconds), the Statue of Freedom glints, and flags rise and ripple over the Senate and House wings
  - Matching accents: the header logo is a dome that draws itself and glints on hover, loading spinners are a dome drawing itself, and job cards get a gold line along the top on hover
  - Respects reduced-motion settings; plain SVG and CSS, no new dependencies

## 2026-10-13

- Fix HVAPS job titles: 38 of 65 open listings had a section header, "Unknown Position" or a sentence fragment as their title (e.g. "SUMMARY:", "self- starter", "communications team")
  - Section headers ("SUMMARY:", "POSITION OVERVIEW", "Requirements:") are skipped; "POSITION OPENING: DISTRICT DIRECTOR" becomes "District Director"
  - New phrasings: "opening for an <Title>", "The <Title> serves/supports/will", "for a paid Spring 2027 internship position", "to serve as <Title>" without an article
  - Lowercase fragments are only titles when they name a job ("press intern" → "Press Intern"); internship titles include their term ("Fall 2026 Interns")
  - Existing rows get the new titles on the next ingest (matched by MEM number, so no duplicates)
- Run unit tests on pull requests; live scrape tests still run only on pushes to main and manual runs

## 2026-10-12

- Fix job categories: 142 of 342 open jobs were in the wrong one (e.g. 147 "Communications" jobs, mostly interns and staff assistants)
  - Descriptions no longer decide the category from incidental words like "communication skills", "legal requirements" or "security clearance"
  - Office and facilities titles (interns, staff assistants, schedulers, caseworkers, trades) are Operations; Capitol Police jobs are always Security
  - Rule-order fixes ("Consumer Protection" policy advisor, "Business Systems Analyst") and `IT` is matched case-sensitively
  - Existing jobs are re-categorized whenever ingestion sees them again
- Turn on the weekly job-alert newsletter (#41 shipped the signup flow, but the sender never ran)
  - New `newsletter-cron` Railway service, Mondays 11:30 UTC
  - Fix `send_newsletter.py` imports, add `--dry-run`, mask subscriber emails in logs, add tests
  - Escape scraped job titles and office names in digest emails
  - Group digest jobs by category, then list them alphabetically by title (was newest first)

## 2026-10-11

- Rewrite Library of Congress adapter to use loc.gov's JSON API; the HTML career pages now sit behind a Cloudflare challenge
  - Recognizes all vacancy-number spellings in titles, keeps the old title format so existing rows still match
  - Paces detail requests and retries on 429 rate limits
- LoC adapter also retries dropped connections, with a 20s per-request timeout (loc.gov sometimes stalls mid-response)

## 2026-10-10

- Move daily ingestion from GitHub Actions to a Railway cron service (`ingest-cron`)
  - GitHub had disabled the scheduled workflow on 2026-08-04 for repo inactivity, freezing the site
  - Cron now covers all 13 sources, including CSOD (Chromium via `INSTALL_CHROMIUM` build arg) and HVAPS email
  - A source returning 0 jobs is recorded as `empty`, not `success`, so failed scrapes can't close its open jobs
  - GitHub workflow is now tests-only
- Point CBO adapter at `cbo.clayhr.com`; the old `cbo.bizmerlin.net` host now serves a mismatched TLS certificate

## 2026-06-05

- Repo activity ping to keep scheduled GitHub Actions (House jobs ingestion) running

## 2026-03-23

- Add GAO, GPO, and CBO ingestion adapters (#46)
  - GAO and GPO via USAJobs API (agency codes LG00, LP00)
  - CBO via BizMerlin/ClayHR REST API
  - Refactor USAJobs adapter into generic, config-driven `UsajobsAdapter`
  - Wire new sources into all ingest paths (API route, cron job, scrape script)

## 2026-03-19

- Revert Senate adapter to httpx with improved rate-limit handling (#45)
- Use Playwright for Senate detail fetching to bypass 403s (#44)
- Add retry-with-backoff for Senate API rate limiting (#43)

## 2026-03-17

- Add weekly email newsletter feature (#41)
- Fetch full job descriptions from Senate detail API endpoint (#42)

## 2026-03-16

- Add custom domain routing for hill-jobs.org (#40)
- Fix member party lookup mismatches and improve HVAPS title extraction (#39)
- Remove hardcoded Postgres credentials from CLAUDE.md (#38)
- Improve HVAPS PDF parser for internship listings (#37)
- Fix HVAPS email subject MIME decoding in scraper test (#36)

## 2026-03-12

- Add scraping pipeline: 10 sources, GitHub Action, HVAPS email adapter (#33)
- Add database upsert step to GitHub Action with LLM salary extraction (#34)
- Stop storing scraped data in git — DB is source of truth (#35)

## 2026-03-11

- Make frontend LLM-readable: add labels, JSON-LD schema, and a11y improvements (#32)
- Add daily scheduled ingestion via Railway cron job (#31)
- Split committee and subcommittee into separate filters (#30)
- Search all fields: title, organization, location, description (#29)

## 2026-03-10

- Deduplicate organizations endpoint by name (#28)
- Resolve HVAPS member names to canonical MEMBER_PARTIES names (#27)
- Enrich CSOD jobs with detail page data (#26)
- Implement HVAPS PDF ingestion with cross-source dedup (#25)
- Add House CSOD career sites (CAO, Clerk, SAA, Green & Gold) (#24)

## 2026-03-09

- Add organization and committee filters to job search (#22)
- Add salary filter to job search (#21)
- Wire LLM salary extraction into ingestion pipeline (#18, #19)
- Add LLM-based salary extraction with Gemini Flash Lite via OpenRouter (#17)

## 2026-03-08

- Normalize Office of Congresswoman/Congressman names to Rep. format (#16)
- Update source_organization on re-ingestion (#15)
- Add full Congress member lookup table from Congress.gov API (#13)
- Use individual hiring org names for House Dems Resume Bank jobs (#12)
- Organize filters by chamber and show party affiliation for senators (#10)
- Add House Democrats Resume Bank adapter (#9)

## 2026-03-07

- Add FAQ section to homepage (#8)
- Split members into separate filter dropdown (#7)
- Build Cloudflare Workers React frontend for Hill Jobs (#5)
- Configure Railway to build from apps/api Dockerfile (#4)
- Add scraping, search API, and ingestion pipeline (#3)
- Add database layer and Railway deployment infrastructure (#2)
- Scaffold FastAPI backend with job schemas and tests (#1)
