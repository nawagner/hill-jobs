"""Scheduled ingestion cron job.

Runs all server-side adapters (same as POST /api/internal/ingest/run).
Intended to be executed as a Railway cron service daily at 4 AM ET.
"""

import logging
import sys

import httpx
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db import get_engine
from app.ingest.adapters.aoc_usajobs import AocUsajobsAdapter
from app.ingest.adapters.cbo_bizmerlin import CboBizmerlinAdapter
from app.ingest.adapters.house_dems_resumebank import HouseDemsResumebankAdapter
from app.ingest.adapters.loc import LocAdapter
from app.ingest.adapters.senate import SenateAdapter
from app.ingest.adapters.usajobs import UsajobsAdapter, GAO_CONFIG, GPO_CONFIG
from app.ingest.run_all import run_all_sources

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def build_registry(settings: Settings):
    registry = {
        "senate-webscribble": SenateAdapter(),
        "loc-careers": LocAdapter(),
        "house-dems-resumebank": HouseDemsResumebankAdapter(),
    }
    if settings.usajobs_api_key:
        uj_kwargs = dict(
            api_key=settings.usajobs_api_key,
            user_agent_email=settings.usajobs_user_agent_email or "",
        )
        registry["aoc-usajobs"] = AocUsajobsAdapter(**uj_kwargs)
        registry["gao-usajobs"] = UsajobsAdapter(GAO_CONFIG, **uj_kwargs)
        registry["gpo-usajobs"] = UsajobsAdapter(GPO_CONFIG, **uj_kwargs)

    registry["cbo-bizmerlin"] = CboBizmerlinAdapter()
    return registry


def main():
    settings = Settings()
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    registry = build_registry(settings)
    logger.info("Starting scheduled ingestion for %d sources", len(registry))

    with httpx.Client(timeout=60.0) as client:
        results = run_all_sources(session, registry, client)

    session.close()

    for name, r in results.items():
        status = f"  {name}: {r.status} — found={r.jobs_found} created={r.created} updated={r.updated} closed={r.closed}"
        if r.error:
            status += f" error={r.error}"
        print(status)

    if any(r.status == "error" for r in results.values()):
        logger.error("One or more sources failed")
        sys.exit(1)

    logger.info("Scheduled ingestion complete")


if __name__ == "__main__":
    main()
