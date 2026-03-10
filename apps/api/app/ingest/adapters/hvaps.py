"""HVAPS (House Vacancy Announcement and Placement Service) adapter.

Parses job listings from HVAPS PDF bulletins. Unlike other adapters, this is
triggered manually via a dedicated endpoint with a PDF URL, not via the
automated adapter registry.
"""

import logging

from app.ingest.hvaps_pdf_parser import parse_hvaps_pdf
from app.ingest.salary_parser import parse_salary_from_text
from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

SOURCE_SYSTEM = "house-hvaps"


def parse_hvaps_source_jobs(pdf_bytes: bytes, pdf_url: str) -> list[SourceJob]:
    """Parse an HVAPS PDF and return SourceJob objects ready for upsert."""
    parsed = parse_hvaps_pdf(pdf_bytes)
    jobs: list[SourceJob] = []

    for item in parsed:
        try:
            jobs.append(_to_source_job(item, pdf_url))
        except Exception:
            logger.exception(
                "Failed to convert HVAPS listing %s to SourceJob",
                item.get("source_job_id"),
            )

    logger.info("Converted %d HVAPS listings to SourceJobs", len(jobs))
    return jobs


def _to_source_job(item: dict, pdf_url: str) -> SourceJob:
    description_text = item["description_text"]

    # Try to extract salary from the salary text field or description
    salary_min = None
    salary_max = None
    salary_period = None
    salary_text = item.get("salary_text") or ""
    parsed_salary = parse_salary_from_text(salary_text) or parse_salary_from_text(
        description_text
    )
    if parsed_salary:
        salary_min = parsed_salary.min_value
        salary_max = parsed_salary.max_value
        salary_period = parsed_salary.period

    # Wrap plain text in basic HTML paragraphs
    description_html = "\n".join(
        f"<p>{line}</p>" for line in description_text.split("\n") if line.strip()
    )

    return SourceJob(
        source_system=SOURCE_SYSTEM,
        source_organization=item["organization"],
        source_job_id=item["source_job_id"],
        source_url=pdf_url,
        title=item["title"],
        description_html=description_html,
        description_text=description_text,
        location_text=item.get("location"),
        employment_type=None,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_period=salary_period,
        raw_payload=item,
    )
