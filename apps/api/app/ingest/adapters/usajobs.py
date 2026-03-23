"""Generic USAJobs adapter – config-driven for multiple agencies.

Each agency that posts on USAJobs gets its own ``UsajobsConfig`` and a
corresponding ``UsajobsAdapter`` instance.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

SEARCH_URL = "https://data.usajobs.gov/api/Search"


@dataclass(frozen=True)
class UsajobsConfig:
    source_system: str
    source_organization: str
    # Use *either* organization_code (preferred) or keyword for the search.
    organization_code: str | None = None
    keyword: str | None = None


# ── Agency configs ────────────────────────────────────────────────────
AOC_CONFIG = UsajobsConfig(
    source_system="aoc-usajobs",
    source_organization="Architect of the Capitol",
    keyword="Architect of the Capitol",
)

GAO_CONFIG = UsajobsConfig(
    source_system="gao-usajobs",
    source_organization="Government Accountability Office",
    organization_code="LG00",
)

GPO_CONFIG = UsajobsConfig(
    source_system="gpo-usajobs",
    source_organization="Government Publishing Office",
    organization_code="LP00",
)


class UsajobsAdapter:
    """Fetch jobs from USAJobs for a single agency."""

    def __init__(self, config: UsajobsConfig, *, api_key: str, user_agent_email: str = ""):
        self.config = config
        self.source_system = config.source_system
        self.api_key = api_key
        self.user_agent_email = user_agent_email

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        if not self.api_key:
            logger.warning("USAJobs API key not configured, skipping %s", self.source_system)
            return []

        jobs: list[SourceJob] = []
        page = 1
        while True:
            data = self._fetch_page(client, page)
            items = data.get("SearchResult", {}).get("SearchResultItems", [])
            if not items:
                break

            for item in items:
                job = _parse_result(item, self.config)
                if job:
                    jobs.append(job)

            total_pages = int(
                data.get("SearchResult", {})
                .get("UserArea", {})
                .get("NumberOfPages", "1")
            )
            if page >= total_pages:
                break
            page += 1

        logger.info("%s: found %d jobs", self.source_system, len(jobs))
        return jobs

    def _fetch_page(self, client: httpx.Client, page: int) -> dict:
        params: dict[str, str | int] = {
            "ResultsPerPage": 25,
            "Page": page,
        }
        if self.config.organization_code:
            params["Organization"] = self.config.organization_code
        if self.config.keyword:
            params["Keyword"] = self.config.keyword

        resp = client.get(
            SEARCH_URL,
            params=params,
            headers={
                "Authorization-Key": self.api_key,
                "User-Agent": self.user_agent_email,
            },
        )
        resp.raise_for_status()
        return resp.json()


def _parse_result(item: dict, config: UsajobsConfig) -> SourceJob | None:
    desc = item.get("MatchedObjectDescriptor", {})
    if not desc:
        return None

    org_name = desc.get("OrganizationName", "")
    # Safety filter: skip results that don't belong to the expected org.
    if config.keyword and config.source_organization not in org_name:
        return None

    title = desc.get("PositionTitle", "")
    position_id = desc.get("PositionID", "")
    position_uri = desc.get("PositionURI", "")
    location = desc.get("PositionLocationDisplay", "")

    # Salary
    salary_min = None
    salary_max = None
    salary_period = None
    remuneration = desc.get("PositionRemuneration", [])
    if remuneration:
        r = remuneration[0]
        min_pay = r.get("MinimumRange", "")
        max_pay = r.get("MaximumRange", "")
        rate_code = r.get("RateIntervalCode", "")
        if min_pay:
            salary_min = float(min_pay)
        if max_pay:
            salary_max = float(max_pay)
        if rate_code == "PA":
            salary_period = "yearly"
        elif rate_code == "PH":
            salary_period = "hourly"

    # Dates
    posted_at = _parse_iso_date(desc.get("PublicationStartDate"))
    closing_at = _parse_iso_date(desc.get("ApplicationCloseDate"))

    # Description
    user_area = desc.get("UserArea", {}).get("Details", {})
    summary = user_area.get("JobSummary", "")
    duties = user_area.get("MajorDuties", [])
    desc_text = summary
    if duties:
        desc_text += "\n\n" + "\n".join(f"- {d}" for d in duties)

    grade_info = desc.get("JobGrade", [{}])
    grade = grade_info[0].get("Code", "") if grade_info else ""

    return SourceJob(
        source_system=config.source_system,
        source_organization=config.source_organization,
        source_job_id=position_id,
        source_url=position_uri,
        title=title,
        description_html=f"<p>{summary}</p>",
        description_text=desc_text,
        location_text=location,
        employment_type=grade,
        posted_at=posted_at,
        closing_at=closing_at,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_period=salary_period,
        raw_payload=item,
    )


def _parse_iso_date(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
