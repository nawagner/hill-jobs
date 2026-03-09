import logging
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

API_URL = "https://resumebank.domewatch.us/api/v4/jobs"
SOURCE_SYSTEM = "house-dems-resumebank"
SOURCE_ORG = "House Democrats"
BASE_JOB_URL = "https://resumebank.domewatch.us/jobs/"


class HouseDemsResumebankAdapter:
    source_system = SOURCE_SYSTEM

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        resp = client.get(API_URL)
        resp.raise_for_status()
        data = resp.json()
        logger.info("House Dems Resume Bank API: found %d listings", len(data))
        return parse_jobs(data)


def parse_jobs(data: list[dict]) -> list[SourceJob]:
    jobs: list[SourceJob] = []
    for item in data:
        try:
            jobs.append(_parse_job(item))
        except Exception:
            logger.exception(
                "Failed to parse House Dems job: %s", item.get("id")
            )
    return jobs


def _parse_job(item: dict) -> SourceJob:
    desc_html = item.get("description", "")
    desc_text = BeautifulSoup(desc_html, "html.parser").get_text(
        separator=" ", strip=True
    )

    salary_min, salary_max, salary_period = _extract_salary(item)

    org = _extract_org(item)

    return SourceJob(
        source_system=SOURCE_SYSTEM,
        source_organization=org,
        source_job_id=str(item["id"]),
        source_url=f"{BASE_JOB_URL}{item['id']}",
        title=item["title"],
        description_html=desc_html,
        description_text=desc_text,
        location_text=_parse_location(item.get("jobLocation", {})),
        employment_type=_normalize_employment_type(item.get("employmentType")),
        posted_at=_parse_datetime(item.get("createdAt")),
        closing_at=_parse_datetime(item.get("validThrough")),
        salary_min=salary_min,
        salary_max=salary_max,
        salary_period=salary_period,
        raw_payload=item,
    )


def _extract_org(item: dict) -> str:
    """Extract the hiring organization name from the job payload.

    The API returns names like "Mullin, Kevin - Rep." for individual members
    and plain names like "House Rules Committee" for committees/caucuses.
    Member names are converted to "Rep. First Last" format.
    """
    ho = item.get("hiringOrganization", {})
    name_obj = ho.get("name", {})
    text = name_obj.get("text", "") if isinstance(name_obj, dict) else str(name_obj)
    if not text:
        return SOURCE_ORG

    # "Last, First - Rep." → "Rep. First Last"
    if text.endswith(" - Rep."):
        name_part = text[: -len(" - Rep.")]
        parts = name_part.split(", ", 1)
        if len(parts) == 2:
            return f"Rep. {parts[1]} {parts[0]}"
        return f"Rep. {name_part}"

    # "Office of Congresswoman/Congressman First Last" → "Rep. First Last"
    for prefix in ("Office of Congresswoman ", "Office of Congressman "):
        if text.startswith(prefix):
            return f"Rep. {text[len(prefix):]}"

    return text


def _extract_salary(item: dict) -> tuple[float | None, float | None, str | None]:
    base_salary = item.get("baseSalary")
    if not base_salary or not isinstance(base_salary, dict):
        return None, None, None
    value_obj = base_salary.get("value", {})
    if not isinstance(value_obj, dict):
        return None, None, None
    raw_val = value_obj.get("value", "")
    if not raw_val:
        return None, None, None
    numeric = float(str(raw_val).replace(",", ""))
    unit = value_obj.get("unitText", "")
    if unit == "HOUR":
        period = "hourly"
    else:
        period = "yearly"
    return numeric, numeric, period


def _parse_location(loc: dict) -> str | None:
    if not loc:
        return None
    addr = loc.get("address", {})
    city = addr.get("addressLocality")
    region = addr.get("addressRegion")
    if city and region:
        return f"{city}, {region}"
    return city or region or None


def _normalize_employment_type(value: str | None) -> str | None:
    if not value:
        return None
    if value == "FULL_TIME":
        return "Full Time"
    return value


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
