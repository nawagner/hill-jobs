import logging
import re

import httpx
from bs4 import BeautifulSoup

from app.ingest.salary_parser import parse_salary_from_text
from app.lib.fetch_html import fetch_page
from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

LISTING_URL = "https://www.loc.gov/careers/?all=true"
SOURCE_SYSTEM = "loc-careers"
SOURCE_ORG = "Library of Congress"

_MONEY_RE = re.compile(r"\$[\d,]+(?:\.\d+)?")
_PERIOD_RE = re.compile(r"per\s+(year|hour|annum)", re.IGNORECASE)


class LocAdapter:
    source_system = SOURCE_SYSTEM

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        html = fetch_page(client, LISTING_URL)
        jobs = parse_listing(html)
        for job in jobs:
            try:
                _enrich_from_detail(client, job)
            except Exception:
                logger.exception(
                    "Failed to fetch LOC detail page for %s", job.source_job_id
                )
        return jobs


def parse_listing(html: str) -> list[SourceJob]:
    soup = BeautifulSoup(html, "lxml")
    jobs: list[SourceJob] = []

    for item in soup.select("li.item"):
        try:
            job = _parse_item(item)
            if job:
                jobs.append(job)
        except Exception:
            logger.exception("Failed to parse LOC item")

    return jobs


def _parse_item(item) -> SourceJob | None:
    title_link = item.select_one("span.item-description-title a")
    if not title_link:
        return None

    full_title = title_link.get_text(strip=True)
    href = title_link.get("href", "")

    # Extract vacancy ID from title like "Reference Librarian (Vacancy#: VAR003224)"
    source_job_id = None
    if "Vacancy#:" in full_title:
        parts = full_title.split("Vacancy#:")
        source_job_id = parts[-1].strip().rstrip(")")
        title = parts[0].strip().rstrip("(").strip()
    else:
        title = full_title

    # Extract dates
    opening_el = item.select_one("li.opening-date span")
    closing_el = item.select_one("li.closing-date span")

    from datetime import datetime

    posted_at = _parse_date(opening_el.get_text(strip=True)) if opening_el else None
    closing_at = _parse_date(closing_el.get_text(strip=True)) if closing_el else None

    # Description
    desc_el = item.select_one("span.item-description-abstract")
    desc_text = desc_el.get_text(strip=True) if desc_el else ""

    # Job type
    type_el = item.select_one("span.original-format")
    employment_type = type_el.get_text(strip=True) if type_el else None

    # Grade
    grade_el = item.select_one("li.grade span")
    grade = grade_el.get_text(strip=True) if grade_el else ""
    if grade:
        title = f"{title} ({grade})"

    salary_min = salary_max = salary_period = None
    parsed_salary = parse_salary_from_text(desc_text)
    if parsed_salary:
        salary_min = parsed_salary.min_value
        salary_max = parsed_salary.max_value
        salary_period = parsed_salary.period

    return SourceJob(
        source_system=SOURCE_SYSTEM,
        source_organization=SOURCE_ORG,
        source_job_id=source_job_id,
        source_url=href,
        title=title,
        description_html=f"<p>{desc_text}</p>",
        description_text=desc_text,
        location_text="Washington, DC",
        employment_type=employment_type,
        posted_at=posted_at,
        closing_at=closing_at,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_period=salary_period,
        raw_payload={"source_url": href, "vacancy_id": source_job_id},
    )


def _parse_date(text: str):
    from datetime import datetime, timezone

    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _enrich_from_detail(client: httpx.Client, job: SourceJob) -> None:
    """Fetch a LOC detail page and enrich the job with salary and description."""
    if not job.source_url:
        return

    html = fetch_page(client, job.source_url)
    soup = BeautifulSoup(html, "lxml")

    # Extract salary from <li><strong>Minimum Salary:</strong> $X per year</li>
    for li in soup.find_all("li"):
        strong = li.find("strong")
        if not strong:
            continue
        label = strong.get_text(strip=True).lower()
        text = li.get_text(strip=True)

        if "minimum salary" in label:
            m = _MONEY_RE.search(text)
            if m:
                job.salary_min = float(m.group().replace("$", "").replace(",", ""))
            p = _PERIOD_RE.search(text)
            if p:
                word = p.group(1).lower()
                job.salary_period = "yearly" if word in ("year", "annum") else "hourly"

        elif "maximum salary" in label:
            m = _MONEY_RE.search(text)
            if m:
                job.salary_max = float(m.group().replace("$", "").replace(",", ""))

    # Extract richer description from detail page
    desc_div = soup.select_one("div.body-text") or soup.select_one("div#content")
    if desc_div:
        paragraphs = desc_div.find_all("p")
        if paragraphs:
            desc_html = "\n".join(str(p) for p in paragraphs)
            desc_text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            if len(desc_text) > len(job.description_text):
                job.description_html = desc_html
                job.description_text = desc_text
