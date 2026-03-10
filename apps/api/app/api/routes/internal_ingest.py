import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import verify_internal_token
from app.config import Settings, get_settings
from app.db import get_db
from app.ingest.adapters.aoc_usajobs import AocUsajobsAdapter
from app.ingest.adapters.house_dems_resumebank import HouseDemsResumebankAdapter
from app.ingest.adapters.hvaps import parse_hvaps_source_jobs
from app.ingest.adapters.loc import LocAdapter
from app.ingest.adapters.senate import SenateAdapter
from app.ingest.mark_missing_jobs import mark_missing_jobs
from app.ingest.run_all import run_all_sources
from app.ingest.source_registry import SourceAdapter
from app.ingest.upsert_jobs import upsert_jobs
from app.models.sync_runs import SourceSyncRun

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/internal")


def build_registry(settings: Settings) -> dict[str, SourceAdapter]:
    # CSOD adapters (house-cao, uscp) require agent-browser and are run
    # locally via scripts/ingest_csod.py instead of on the server.
    registry: dict[str, SourceAdapter] = {
        "senate-webscribble": SenateAdapter(),
        "loc-careers": LocAdapter(),
        "house-dems-resumebank": HouseDemsResumebankAdapter(),
    }
    if settings.usajobs_api_key:
        registry["aoc-usajobs"] = AocUsajobsAdapter(
            api_key=settings.usajobs_api_key,
            user_agent_email=settings.usajobs_user_agent_email or "",
        )
    return registry


@router.post("/ingest/run")
def run_ingest(
    _: None = Depends(verify_internal_token),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    registry = build_registry(settings)
    with httpx.Client(timeout=60.0) as client:
        results = run_all_sources(db, registry, client)

    return {
        "sources": {
            name: {
                "status": r.status,
                "jobs_found": r.jobs_found,
                "created": r.created,
                "updated": r.updated,
                "skipped": r.skipped,
                "closed": r.closed,
                **({"error": r.error} if r.error else {}),
            }
            for name, r in results.items()
        }
    }


@router.post("/ingest/hvaps")
def ingest_hvaps(
    pdf_url: str = Query(..., description="URL of the HVAPS PDF bulletin"),
    _: None = Depends(verify_internal_token),
    db: Session = Depends(get_db),
):
    """Ingest jobs from an HVAPS PDF bulletin.

    Manually triggered with the PDF URL from the weekly HVAPS email.
    """
    source_system = "house-hvaps"
    now = datetime.now(timezone.utc)

    # Record sync run
    sync_run = SourceSyncRun(
        source_system=source_system,
        started_at=now,
        status="running",
    )
    db.add(sync_run)
    db.commit()

    try:
        # Download the PDF
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(pdf_url)
            resp.raise_for_status()
            pdf_bytes = resp.content

        # Parse and upsert
        source_jobs = parse_hvaps_source_jobs(pdf_bytes, pdf_url)
        result = upsert_jobs(db, source_jobs, now)
        closed = mark_missing_jobs(db, source_system, set(result.seen_ids), now)

        sync_run.status = "success"
        sync_run.finished_at = datetime.now(timezone.utc)
        sync_run.jobs_found = len(source_jobs)
        sync_run.jobs_created = result.created
        sync_run.jobs_updated = result.updated
        sync_run.jobs_closed = closed
        db.commit()

        return {
            "status": "success",
            "jobs_found": len(source_jobs),
            "created": result.created,
            "updated": result.updated,
            "skipped": result.skipped,
            "closed": closed,
        }
    except Exception as e:
        logger.exception("HVAPS ingest failed: %s", e)
        sync_run.status = "error"
        sync_run.finished_at = datetime.now(timezone.utc)
        sync_run.error_message = str(e)
        db.commit()
        raise
