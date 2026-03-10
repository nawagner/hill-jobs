"""Run CSOD adapters locally (they require agent-browser)."""

import logging
import sys

import httpx

from app.db import get_engine
from app.ingest.adapters.csod import (
    HOUSE_CAO_CONFIG,
    HOUSE_CLERK_CONFIG,
    HOUSE_GREEN_GOLD_CONFIG,
    HOUSE_SAA_CONFIG,
    USCP_CONFIG,
    CsodAdapter,
)
from app.ingest.run_all import run_all_sources
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

CONFIGS = [
    HOUSE_CAO_CONFIG,
    HOUSE_CLERK_CONFIG,
    HOUSE_SAA_CONFIG,
    HOUSE_GREEN_GOLD_CONFIG,
    USCP_CONFIG,
]


def main():
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    session = Session()

    registry = {cfg.source_system: CsodAdapter(cfg) for cfg in CONFIGS}

    with httpx.Client(timeout=60.0) as client:
        results = run_all_sources(session, registry, client)

    session.close()

    for name, r in results.items():
        status = f"  {name}: {r.status} — found={r.jobs_found} created={r.created} updated={r.updated} closed={r.closed}"
        if r.error:
            status += f" error={r.error}"
        print(status)

    if any(r.status == "error" for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
