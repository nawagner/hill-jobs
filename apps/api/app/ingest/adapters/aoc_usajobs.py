import logging
from datetime import datetime, timezone

import httpx

from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

SEARCH_URL = "https://data.usajobs.gov/api/Search"
SOURCE_SYSTEM = "aoc-usajobs"
SOURCE_ORG = "Architect of the Capitol"


class AocUsajobsAdapter:
    source_system = SOURCE_SYSTEM

    def __init__(self, api_key: str, user_agent_email: str = ""):
        self.api_key = api_key
        self.user_agent_email = user_agent_email

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        if not self.api_key:
            logger.warning("USAJobs API key not configured, skipping AOC adapter")
            return []

        jobs: list[SourceJob] = []
        page = 1
        while True:
            data = self._fetch_page(client, page)
            items = data.get("SearchResult", {}).get("SearchResultItems", [])
            if not items:
                break

            for item in items:
                job = _parse_result(item)
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

        logger.info("AOC USAJobs: found %d jobs", len(jobs))
        return jobs

    def _fetch_page(self, client: httpx.Client, page: int) -> dict:
        resp = client.get(
            SEARCH_URL,
            params={
                "Keyword": "Architect of the Capitol",
                "ResultsPerPage": 25,
                "Page": page,
            },
            headers={
                "Authorization-Key": self.api_key,
                "User-Agent": self.user_agent_email,
            },
        )
        resp.raise_for_status()
        return resp.json()


def _parse_result(item: dict) -> SourceJob | None:
    desc = item.get("MatchedObjectDescriptor", {})
    if not desc:
        return None

    org_name = desc.get("OrganizationName", "")
    if "Architect of the Capitol" not in org_name:
        return None

    title = desc.get("PositionTitle", "")
    position_id = desc.get("PositionID", "")
    position_uri = desc.get("PositionURI", "")

    location = desc.get("PositionLocationDisplay", "")

    # Salary info
    salary = ""
    remuneration = desc.get("PositionRemuneration", [])
    if remuneration:
        r = remuneration[0]
        min_pay = r.get("MinimumRange", "")
        max_pay = r.get("MaximumRange", "")
        rate = r.get("Description", "")
        if min_pay and max_pay:
            salary = f"${min_pay} - ${max_pay} {rate}"

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
        source_system=SOURCE_SYSTEM,
        source_organization=SOURCE_ORG,
        source_job_id=position_id,
        source_url=position_uri,
        title=title,
        description_html=f"<p>{summary}</p>",
        description_text=desc_text,
        location_text=location,
        employment_type=grade,
        posted_at=posted_at,
        closing_at=closing_at,
        raw_payload=item,
    )


def _parse_iso_date(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
