"""Manual adapter – serves the hand-added listings in app/data/manual_jobs.py."""

import html
import logging
from datetime import datetime, timezone

import httpx

from app.data.manual_jobs import MANUAL_JOBS
from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

SOURCE_SYSTEM = "manual"


class ManualAdapter:
    source_system = SOURCE_SYSTEM
    # An empty list means every manual listing was taken down, not a failed
    # fetch, so the sync closes them.
    empty_is_authoritative = True

    def __init__(self, entries: list[dict] | None = None):
        self.entries = MANUAL_JOBS if entries is None else entries

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        now = datetime.now(timezone.utc)
        jobs = [
            _to_source_job(entry)
            for entry in self.entries
            if entry.get("closing_at") is None or entry["closing_at"] > now
        ]
        logger.info("Manual: %d open listings", len(jobs))
        return jobs


def _to_source_job(entry: dict) -> SourceJob:
    paragraphs = entry["description"]
    return SourceJob(
        source_system=SOURCE_SYSTEM,
        source_organization=entry["source_organization"],
        source_job_id=entry["source_job_id"],
        source_url=entry["source_url"],
        title=entry["title"],
        description_html="\n".join(f"<p>{html.escape(p)}</p>" for p in paragraphs),
        description_text="\n".join(paragraphs),
        location_text=entry.get("location_text"),
        posted_at=entry.get("posted_at"),
        closing_at=entry.get("closing_at"),
        raw_payload={"source_job_id": entry["source_job_id"]},
    )
