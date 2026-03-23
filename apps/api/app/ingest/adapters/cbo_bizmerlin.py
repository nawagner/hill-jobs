"""CBO job board adapter – fetches positions from BizMerlin (ClayHR) API."""

import logging
from datetime import datetime, timezone

import httpx

from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

POSITIONS_URL = "https://cbo.bizmerlin.net/job-board/position/api/getpositions"
JOBBOARD_BASE = "https://cbo.bizmerlin.net/jobboard/#/position/view"
SOURCE_SYSTEM = "cbo-bizmerlin"
SOURCE_ORG = "Congressional Budget Office"


class CboBizmerlinAdapter:
    source_system = SOURCE_SYSTEM

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        resp = client.get(POSITIONS_URL, params={"status": "OPEN"})
        resp.raise_for_status()
        data = resp.json()

        positions = data.get("positionModelList", [])
        jobs: list[SourceJob] = []
        for pos in positions:
            job = _parse_position(pos)
            if job:
                jobs.append(job)

        logger.info("CBO BizMerlin: found %d jobs", len(jobs))
        return jobs


def _parse_position(pos: dict) -> SourceJob | None:
    position_id = pos.get("positionid")
    uid = pos.get("positionUID", "")
    title = (pos.get("name") or "").strip()
    if not title or not position_id:
        return None

    description_html = pos.get("description") or ""
    # Strip HTML tags for plain-text version
    import re
    description_text = re.sub(r"<[^>]+>", " ", description_html)
    description_text = re.sub(r"\s+", " ", description_text).strip()

    # Location
    loc_model = pos.get("locationModel") or {}
    location = loc_model.get("locationName", "")
    addr_list = loc_model.get("addressModelList") or []
    if addr_list:
        addr = addr_list[0]
        city = addr.get("city", "")
        state = addr.get("state", "")
        if city and state:
            location = f"{city}, {state}"

    # Dates
    posted_at = _parse_date(pos.get("datePublish"))
    closing_at = _parse_date(pos.get("applicationDueDate"))

    # Department
    dept = (pos.get("departmentModel") or {}).get("name", "")
    if dept:
        description_text = f"Department: {dept}\n\n{description_text}"

    seo_url = pos.get("seoUrl", "")
    source_url = f"{JOBBOARD_BASE}/{position_id}/{seo_url}"

    return SourceJob(
        source_system=SOURCE_SYSTEM,
        source_organization=SOURCE_ORG,
        source_job_id=str(position_id),
        source_url=source_url,
        title=title,
        description_html=description_html,
        description_text=description_text,
        location_text=location or None,
        posted_at=posted_at,
        closing_at=closing_at,
        raw_payload=pos,
    )


def _parse_date(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
