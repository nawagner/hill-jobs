#!/usr/bin/env python3
"""Read scraped JSON files and upsert into the database.

Usage:
  DATABASE_URL=... python scripts/upsert_scraped.py [--input-dir data/scraped]
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from app.db import get_engine, get_session
from app.ingest.mark_missing_jobs import mark_missing_jobs
from app.ingest.upsert_jobs import upsert_jobs
from app.models.sync_runs import SourceSyncRun
from app.schemas.ingest import SourceJob

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def load_source_jobs(json_path: Path) -> list[SourceJob]:
    """Load a scraped JSON file and convert to SourceJob objects."""
    data = json.loads(json_path.read_text())
    return [SourceJob.model_validate(raw) for raw in data]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="data/scraped")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        logger.error("Input directory %s does not exist", input_dir)
        sys.exit(1)

    # Collect all per-source JSON files (skip all_jobs.json)
    json_files = sorted(
        f for f in input_dir.glob("*.json") if f.name != "all_jobs.json"
    )

    if not json_files:
        logger.warning("No JSON files found in %s", input_dir)
        sys.exit(0)

    engine = get_engine()
    SessionLocal = get_session()
    session = SessionLocal()

    # Collect per-source results for the summary
    rows: list[dict] = []

    try:
        for json_file in json_files:
            source_name = json_file.stem
            now = datetime.now(timezone.utc)

            source_jobs = load_source_jobs(json_file)
            if not source_jobs:
                logger.info("Skipping %s — no jobs", source_name)
                rows.append({"source": source_name, "found": 0, "created": 0,
                             "updated": 0, "unchanged": 0, "closed": 0, "error": ""})
                continue

            source_system = source_jobs[0].source_system

            # Record the sync run
            sync_run = SourceSyncRun(
                source_system=source_system,
                started_at=now,
                status="running",
            )
            session.add(sync_run)
            session.commit()

            try:
                result = upsert_jobs(session, source_jobs, now)
                closed = mark_missing_jobs(
                    session, source_system, set(result.seen_ids), now
                )

                sync_run.status = "success"
                sync_run.finished_at = datetime.now(timezone.utc)
                sync_run.jobs_found = len(source_jobs)
                sync_run.jobs_created = result.created
                sync_run.jobs_updated = result.updated
                sync_run.jobs_closed = closed
                session.commit()

                rows.append({
                    "source": source_system, "found": len(source_jobs),
                    "created": result.created, "updated": result.updated,
                    "unchanged": result.unchanged, "closed": closed, "error": "",
                })

                logger.info(
                    "%s: found=%d created=%d updated=%d unchanged=%d skipped=%d closed=%d",
                    source_system, len(source_jobs), result.created,
                    result.updated, result.unchanged, result.skipped, closed,
                )
            except Exception as e:
                logger.exception("Failed to upsert %s: %s", source_system, e)
                sync_run.status = "error"
                sync_run.finished_at = datetime.now(timezone.utc)
                sync_run.error_message = str(e)
                session.commit()
                rows.append({
                    "source": source_system, "found": len(source_jobs),
                    "created": 0, "updated": 0, "unchanged": 0, "closed": 0,
                    "error": str(e)[:60],
                })

        # Print markdown summary (captured by the workflow for GITHUB_STEP_SUMMARY)
        total_created = sum(r["created"] for r in rows)
        total_updated = sum(r["updated"] for r in rows)
        total_closed = sum(r["closed"] for r in rows)
        total_found = sum(r["found"] for r in rows)

        print("\n# Database Upsert Results\n")
        print("| Source | Found | New | Updated | Unchanged | Closed | Error |")
        print("|--------|------:|----:|--------:|----------:|-------:|-------|")
        for r in rows:
            print(f"| {r['source']} | {r['found']} | {r['created']} | {r['updated']} | {r['unchanged']} | {r['closed']} | {r['error']} |")
        print(f"\n**Totals: {total_found} found, {total_created} new, {total_updated} updated, {total_closed} closed**")

    finally:
        session.close()


if __name__ == "__main__":
    main()
