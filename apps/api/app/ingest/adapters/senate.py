import logging
import re
import time
from datetime import datetime, timezone

import httpx

from app.ingest.salary_parser import parse_salary_from_text
from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

BASE_URL = "https://careers.employment.senate.gov"
API_URL = f"{BASE_URL}/api/v1/jobs"
DETAIL_URL = f"{BASE_URL}/api/v1/jobs"  # + /{id}
SOURCE_SYSTEM = "senate-webscribble"

_BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")


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
            time.sleep(2.0)

        logger.info("Senate API: found %d job listings", len(all_items))

        jobs: list[SourceJob] = []
        for item in all_items:
            try:
                job = self._parse_with_detail(client, item)
                jobs.append(job)
            except Exception:
                logger.exception("Failed to parse Senate job: %s", item.get("url"))
        return jobs

    def _parse_with_detail(self, client: httpx.Client, item: dict) -> SourceJob:
        job_id = item.get("id")
        desc_html = ""
        if job_id:
            try:
                time.sleep(1.0)
                resp = client.get(
                    f"{DETAIL_URL}/{job_id}",
                    headers={"User-Agent": _BROWSER_UA},
                )
                resp.raise_for_status()
                detail = resp.json().get("data", {})
                desc_html = detail.get("description", "")
            except Exception:
                logger.warning("Failed to fetch detail for job %s, using short description", job_id)

        return _parse_api_job(item, desc_html)

    def _fetch_page(self, client: httpx.Client, page: int) -> dict:
        resp = client.get(
            API_URL,
            params={"page": page, "per_page": 25},
            headers={"User-Agent": _BROWSER_UA},
        )
        resp.raise_for_status()
        return resp.json()


def _parse_api_job(item: dict, detail_html: str = "") -> SourceJob:
    title = item.get("title", "")
    url = item.get("url", "")
    job_id = str(item.get("id", ""))
    location = item.get("location", "Washington, DC")
    short_desc = item.get("shortDescription", "")
    company = item.get("company", {})
    organization = company.get("name", "U.S. Senate")
    posted_date = _parse_date(item.get("posted_date"))

    if detail_html:
        desc_html = detail_html
        desc_text = _strip_html(detail_html)
    else:
        desc_html = f"<p>{short_desc}</p>"
        desc_text = short_desc

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


def _strip_html(html: str) -> str:
    text = _HTML_TAG_RE.sub("", html)
    return " ".join(text.split())


def _extract_salary(item: dict) -> tuple[float | None, float | None, str | None]:
    for block in item.get("customBlockList", []):
        if block.get("path") == "approx_salary_text" and block.get("value"):
            parsed = parse_salary_from_text(block["value"])
            if parsed:
                return parsed.min_value, parsed.max_value, parsed.period
            break
    return None, None, None


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
