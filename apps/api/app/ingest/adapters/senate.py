import logging
import time
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from app.ingest.salary_parser import parse_salary_from_text
from app.lib.fetch_html import fetch_page
from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

BASE_URL = "https://careers.employment.senate.gov"
API_URL = f"{BASE_URL}/api/v1/jobs"
SOURCE_SYSTEM = "senate-webscribble"

_BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class SenateAdapter:
    source_system = SOURCE_SYSTEM

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        all_items: list[dict] = []
        page = 1
        while True:
            data = self._fetch_page(client, page)
            items = data.get("data", [])
            if not items:
                break
            all_items.extend(items)
            meta = data.get("meta", {})
            last_page = meta.get("last_page", 1)
            if page >= last_page:
                break
            page += 1

        logger.info("Senate API: found %d job listings", len(all_items))

        jobs: list[SourceJob] = []
        for item in all_items:
            try:
                job = _parse_api_job(item, client)
                jobs.append(job)
            except Exception:
                logger.exception("Failed to parse Senate job: %s", item.get("url"))
            time.sleep(1.0)
        return jobs

    def _fetch_page(self, client: httpx.Client, page: int) -> dict:
        resp = client.get(
            API_URL,
            params={"page": page, "per_page": 25},
            headers={"User-Agent": _BROWSER_UA},
        )
        resp.raise_for_status()
        return resp.json()


def _parse_api_job(item: dict, client: httpx.Client) -> SourceJob:
    title = item.get("title", "")
    url = item.get("url", "")
    job_id = str(item.get("id", ""))
    location = item.get("location", "Washington, DC")
    short_desc = item.get("shortDescription", "")
    company = item.get("company", {})
    organization = company.get("name", "U.S. Senate")
    posted_date = _parse_date(item.get("posted_date"))

    # Fetch full description from detail page
    desc_html = ""
    desc_text = short_desc
    if url:
        try:
            html = fetch_page(client, url)
            desc_html, desc_text = _extract_description(html)
        except Exception:
            logger.debug("Could not fetch detail for %s", url)
            desc_html = f"<p>{short_desc}</p>"

    sal_min, sal_max, sal_period = _extract_salary(item)

    return SourceJob(
        source_system=SOURCE_SYSTEM,
        source_organization=organization,
        source_job_id=job_id,
        source_url=url,
        title=title,
        description_html=desc_html,
        description_text=desc_text or short_desc,
        location_text=location,
        posted_at=posted_date,
        salary_min=sal_min,
        salary_max=sal_max,
        salary_period=sal_period,
        raw_payload=item,
    )


def _extract_salary(item: dict) -> tuple[float | None, float | None, str | None]:
    for block in item.get("customBlockList", []):
        if block.get("path") == "approx_salary_text" and block.get("value"):
            parsed = parse_salary_from_text(block["value"])
            if parsed:
                return parsed.min_value, parsed.max_value, parsed.period
            break
    return None, None, None


def _extract_description(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    desc_el = soup.select_one(".job-description")
    if desc_el:
        return str(desc_el), desc_el.get_text(separator=" ", strip=True)
    return "", ""


def parse_api_response(data: dict) -> list[dict]:
    """Parse the API response and return the list of job dicts."""
    return data.get("data", [])


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
