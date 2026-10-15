"""Scheduled ingestion cron job.

Runs every source adapter, including the Playwright-based CSOD sites and the
HVAPS Gmail adapter, and upserts results directly into the database.
Executed daily by the `ingest-cron` Railway service (built from Dockerfile
with INSTALL_CHROMIUM=1).
"""

import logging
import sys
from pathlib import Path

import httpx
from sqlalchemy.orm import sessionmaker

# Make `app` importable when run as `python scripts/cron_ingest.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings
from app.db import get_engine
from app.ingest.adapters.aoc_usajobs import AocUsajobsAdapter
from app.ingest.adapters.cbo_bizmerlin import CboBizmerlinAdapter
from app.ingest.adapters.csod import (
    CsodAdapter,
    HOUSE_CAO_CONFIG,
    HOUSE_CLERK_CONFIG,
    HOUSE_GREEN_GOLD_CONFIG,
    HOUSE_SAA_CONFIG,
    USCP_CONFIG,
)
from app.ingest.adapters.house_dems_resumebank import HouseDemsResumebankAdapter
from app.ingest.adapters.hvaps_email import HvapsEmailAdapter
from app.ingest.adapters.loc import LocAdapter
from app.ingest.adapters.senate import SenateAdapter
from app.ingest.adapters.usajobs import UsajobsAdapter, GAO_CONFIG, GPO_CONFIG
from app.ingest.run_all import run_all_sources

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# Sources that may legitimately return 0 jobs (no openings, or no credentials).
# CSOD sites aren't listed: they only come back empty when the site confirms
# 0 openings, which counts as a success, and a failed scrape raises.
ALLOW_EMPTY = {
    "aoc-usajobs",
    "gao-usajobs",
    "gpo-usajobs",
    "cbo-bizmerlin",
    "house-hvaps",
}


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
    # After house-dems-resumebank so cross-source dedup matches existing rows.
    registry["house-hvaps"] = HvapsEmailAdapter()

    # Browser-based sources last: slowest and most likely to fail.
    for config in (
        HOUSE_CAO_CONFIG,
        HOUSE_CLERK_CONFIG,
        HOUSE_SAA_CONFIG,
        HOUSE_GREEN_GOLD_CONFIG,
        USCP_CONFIG,
    ):
        registry[config.source_system] = CsodAdapter(config)
    return registry


def main():
    settings = Settings()
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    registry = build_registry(settings)
    logger.info("Starting scheduled ingestion for %d sources", len(registry))

    try:
        with httpx.Client(timeout=60.0) as client:
            results = run_all_sources(session, registry, client)
    finally:
        session.close()
        engine.dispose()

    failures = []
    for name, r in results.items():
        status = f"  {name}: {r.status} — found={r.jobs_found} created={r.created} updated={r.updated} closed={r.closed}"
        if r.error:
            status += f" error={r.error}"
        print(status)
        if r.status == "error" or (r.status == "empty" and name not in ALLOW_EMPTY):
            failures.append(name)

    if failures:
        logger.error("Sources failed or returned no jobs: %s", ", ".join(failures))
        sys.exit(1)

    logger.info("Scheduled ingestion complete")


if __name__ == "__main__":
    main()
