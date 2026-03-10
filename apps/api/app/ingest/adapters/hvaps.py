"""HVAPS (House Vacancy Announcement and Placement Service) adapter.

Parses job listings from HVAPS PDF bulletins. Unlike other adapters, this is
triggered manually via a dedicated endpoint with a PDF URL, not via the
automated adapter registry.
"""

import logging
import re

from app.data.member_parties import MEMBER_PARTIES
from app.ingest.hvaps_pdf_parser import parse_hvaps_pdf
from app.ingest.salary_parser import parse_salary_from_text
from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

SOURCE_SYSTEM = "house-hvaps"

# Build a last-name → canonical-name lookup for Representatives.
# Handles cases where HVAPS uses a different name variant than the canonical list
# (e.g., "Rep. Gilbert R. Cisneros Jr." vs canonical "Rep. Gilbert Ray Cisneros").
_LAST_NAME_TO_CANONICAL: dict[str, list[str]] = {}
for _name in MEMBER_PARTIES:
    if not _name.startswith("Rep. "):
        continue
    # Extract last name: last whitespace-separated token, ignoring suffixes
    _parts = _name[5:].split()
    _last = _parts[-1] if _parts else ""
    if _last.rstrip(".") in ("Jr", "Sr", "II", "III", "IV"):
        _last = _parts[-2] if len(_parts) >= 2 else _last
    _last_lower = _last.lower()
    _LAST_NAME_TO_CANONICAL.setdefault(_last_lower, []).append(_name)


def _resolve_canonical_name(name: str) -> str:
    """Resolve an HVAPS-extracted Rep name to the canonical MEMBER_PARTIES name.

    Falls back to the original name if no match or ambiguous.
    """
    if not name.startswith("Rep. "):
        return name

    # Exact match — already canonical
    if name in MEMBER_PARTIES:
        return name

    # Extract last name from the HVAPS name
    parts = name[5:].split()
    last = parts[-1] if parts else ""
    if last.rstrip(".") in ("Jr", "Sr", "II", "III", "IV"):
        last = parts[-2] if len(parts) >= 2 else last

    candidates = _LAST_NAME_TO_CANONICAL.get(last.lower(), [])
    if len(candidates) == 1:
        return candidates[0]

    # Multiple candidates — try matching first name initial
    if len(candidates) > 1 and len(parts) >= 1:
        first = parts[0].rstrip(".").lower()
        for c in candidates:
            c_first = c[5:].split()[0].rstrip(".").lower()
            if c_first.startswith(first) or first.startswith(c_first):
                return c

    return name


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
        source_organization=_resolve_canonical_name(item["organization"]),
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
