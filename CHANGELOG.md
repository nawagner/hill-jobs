# Changelog

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
