import logging

import httpx
from bs4 import BeautifulSoup

from app.lib.fetch_html import fetch_page
from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

LISTING_URL = "https://www.loc.gov/careers/?all=true"
SOURCE_SYSTEM = "loc-careers"
SOURCE_ORG = "Library of Congress"


class LocAdapter:
    source_system = SOURCE_SYSTEM

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        html = fetch_page(client, LISTING_URL)
        return parse_listing(html)


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
