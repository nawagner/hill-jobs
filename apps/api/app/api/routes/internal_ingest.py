import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import verify_internal_token
from app.config import Settings, get_settings
from app.db import get_db
from app.ingest.adapters.aoc_usajobs import AocUsajobsAdapter
from app.ingest.adapters.csod import HOUSE_CAO_CONFIG, USCP_CONFIG, CsodAdapter
from app.ingest.adapters.loc import LocAdapter
from app.ingest.adapters.senate import SenateAdapter
from app.ingest.run_all import run_all_sources
from app.ingest.source_registry import SourceAdapter

router = APIRouter(prefix="/api/internal")


def build_registry(settings: Settings) -> dict[str, SourceAdapter]:
    registry: dict[str, SourceAdapter] = {
        "senate-webscribble": SenateAdapter(),
        "csod-house-cao": CsodAdapter(HOUSE_CAO_CONFIG),
        "csod-uscp": CsodAdapter(USCP_CONFIG),
        "loc-careers": LocAdapter(),
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
                "closed": r.closed,
                **({"error": r.error} if r.error else {}),
            }
            for name, r in results.items()
        }
    }
