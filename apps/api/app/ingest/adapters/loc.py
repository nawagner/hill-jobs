"""Library of Congress careers adapter.

loc.gov's HTML career pages sit behind a Cloudflare bot challenge, but the
JSON view of the same pages (``?fo=json``) is open to non-browser clients.
Don't send a browser User-Agent here (e.g. via ``fetch_page``): that is what
triggers the challenge.
"""

import logging
import re
import time
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

LISTING_URL = "https://www.loc.gov/careers/?fo=json"
SOURCE_SYSTEM = "loc-careers"
SOURCE_ORG = "Library of Congress"
DEFAULT_LOCATION = "Washington, DC"
MAX_PAGES = 10
# loc.gov rate-limits its JSON API (429), so pace the per-job detail requests.
DETAIL_DELAY_SECONDS = 1.0

# Titles end with the vacancy number in a few spellings:
# "(Vacancy#: VAR003371)", "(Vacancy#:VAR003462)", "(Vacancy#VAR003461)"
_VACANCY_RE = re.compile(r"\s*\(\s*Vacancy\s*#?\s*:?\s*([^)]+?)\s*\)\s*$", re.IGNORECASE)
_MONEY_RE = re.compile(r"[\d,]+(?:\.\d+)?")


class LocAdapter:
    source_system = SOURCE_SYSTEM

    def __init__(self, detail_delay: float = DETAIL_DELAY_SECONDS):
        self.detail_delay = detail_delay

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        results: list[dict] = []
        url = LISTING_URL
        for _ in range(MAX_PAGES):
            data = _get_json(client, url)
            results.extend(data.get("results") or [])
            url = (data.get("pagination") or {}).get("next")
            if not url:
                break

        jobs = parse_results(results)
        for i, job in enumerate(jobs):
            if i and self.detail_delay:
                time.sleep(self.detail_delay)
            try:
                apply_detail(job, _get_json(client, _json_url(job.source_url)))
            except Exception:
                logger.exception("Failed to fetch LOC detail for %s", job.source_url)
        return jobs


def _get_json(client: httpx.Client, url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        resp = client.get(url, follow_redirects=True)
        if resp.status_code == 429 and attempt < retries - 1:
            time.sleep(_retry_delay(resp, attempt))
            continue
        resp.raise_for_status()
        return resp.json()
    return {}


def _retry_delay(resp: httpx.Response, attempt: int) -> float:
    try:
        return min(float(resp.headers["Retry-After"]), 60.0)
    except (KeyError, ValueError):
        return 2.0 ** (attempt + 2)


def _json_url(url: str) -> str:
    return f"{url}{'&' if '?' in url else '?'}fo=json"


def parse_results(results: list[dict]) -> list[SourceJob]:
    jobs: list[SourceJob] = []
    for result in results:
        try:
            job = _parse_result(result)
            if job:
                jobs.append(job)
        except Exception:
            logger.exception("Failed to parse LOC result %s", result.get("url"))
    return jobs


def _parse_result(result: dict) -> SourceJob | None:
    item = result.get("item") or {}
    url = result.get("url")
    title = (result.get("title") or "").strip()
    if not url or not title:
        return None

    source_job_id = None
    match = _VACANCY_RE.search(title)
    if match:
        source_job_id = match.group(1)
        title = title[: match.start()].strip()

    # Same "Title (GS-11)" format the HTML scraper produced, so existing rows
    # without a vacancy number keep matching by slug.
    grade = (item.get("grade") or "").strip()
    if grade:
        title = f"{title} ({grade})"

    article = item.get("article") or ""
    subject = result.get("subject") or []

    return SourceJob(
        source_system=SOURCE_SYSTEM,
        source_organization=SOURCE_ORG,
        source_job_id=source_job_id,
        source_url=url,
        title=title,
        description_html=article,
        description_text=_html_to_text(article),
        location_text=DEFAULT_LOCATION,
        employment_type=_employment_type(subject),
        posted_at=_parse_datetime(item.get("opening_date")),
        closing_at=_parse_datetime(item.get("closing_date")),
        raw_payload={
            "source_url": url,
            "vacancy_id": source_job_id,
            "availability": item.get("availability"),
            "grade": grade or None,
            "series": item.get("series"),
            "telework_eligibility": item.get("telework_eligibility"),
            "organization_unit": item.get("lc_organization_unit"),
        },
    )


def apply_detail(job: SourceJob, data: dict) -> None:
    """Fill salary, duty location and the full posting from a detail page's JSON."""
    item = data.get("item") or {}

    salary_min = _parse_money(item.get("minimum_salary"))
    salary_max = _parse_money(item.get("maximum_salary"))
    if salary_min or salary_max:
        job.salary_min = salary_min
        job.salary_max = salary_max
        # Wage-grade (WG/WL) postings list hourly rates.
        job.salary_period = "hourly" if (salary_max or salary_min) < 1000 else "yearly"

    if item.get("duty_location"):
        job.location_text = item["duty_location"]

    article = item.get("article") or ""
    text = _html_to_text(article)
    if len(text) > len(job.description_text):
        job.description_html = article
        job.description_text = text


def _parse_money(value: str | None) -> float | None:
    if not value:
        return None
    match = _MONEY_RE.search(value)
    return float(match.group().replace(",", "")) if match else None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _employment_type(subject: list[str]) -> str | None:
    # e.g. ["permanent"] -> "Permanent", ["nte 120 days", "detail"] -> "NTE 120 days, Detail"
    terms = [s[:1].upper() + s[1:] for s in subject if s]
    return ", ".join(terms).replace("Nte ", "NTE ") or None


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "lxml").get_text("\n", strip=True)
