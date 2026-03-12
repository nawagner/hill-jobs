#!/usr/bin/env python3
"""Read scraped JSON files and upsert into the database.

Usage:
  DATABASE_URL=... python scripts/upsert_scraped.py [--input-dir data/scraped]
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from app.db import get_engine, get_session
from app.ingest.mark_missing_jobs import mark_missing_jobs
from app.ingest.upsert_jobs import JobChange, upsert_jobs
from app.models.sync_runs import SourceSyncRun
from app.schemas.ingest import SourceJob

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class SourceResult:
    source: str
    found: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    closed: int = 0
    error: str = ""
    created_titles: list[str] = field(default_factory=list)
    updated_details: list[JobChange] = field(default_factory=list)
    reopened_titles: list[str] = field(default_factory=list)
    closed_titles: list[str] = field(default_factory=list)


def load_source_jobs(json_path: Path) -> list[SourceJob]:
    """Load a scraped JSON file and convert to SourceJob objects."""
    data = json.loads(json_path.read_text())
    return [SourceJob.model_validate(raw) for raw in data]


def print_summary(rows: list[SourceResult]):
    """Print markdown summary for GitHub step summary."""
    total_created = sum(r.created for r in rows)
    total_updated = sum(r.updated for r in rows)
    total_closed = sum(r.closed for r in rows)
    total_found = sum(r.found for r in rows)

    print("\n# Database Upsert Results\n")
    print("| Source | Found | New | Updated | Unchanged | Closed | Error |")
    print("|--------|------:|----:|--------:|----------:|-------:|-------|")
    for r in rows:
        print(f"| {r.source} | {r.found} | {r.created} | {r.updated} | {r.unchanged} | {r.closed} | {r.error} |")
    print(f"\n**Totals: {total_found} found, {total_created} new, {total_updated} updated, {total_closed} closed**")

    # Details for anything that changed
    all_created = [(r.source, t) for r in rows for t in r.created_titles]
    all_updated = [(r.source, d) for r in rows for d in r.updated_details]
    all_reopened = [(r.source, t) for r in rows for t in r.reopened_titles]
    all_closed = [(r.source, t) for r in rows for t in r.closed_titles]

    if not any([all_created, all_updated, all_reopened, all_closed]):
        print("\nNo changes.")
        return

    print("\n---\n## Changes\n")

    if all_created:
        print(f"<details><summary><b>New jobs ({len(all_created)})</b></summary>\n")
        for source, title in all_created:
            print(f"- **{title}** ({source})")
        print("\n</details>\n")

    if all_updated:
        # Filter out updates that are only description_html/description_text
        # (these change every run due to truncation differences and aren't interesting)
        interesting = [
            (s, d) for s, d in all_updated
            if set(d.changed_fields) - {"description_html", "description_text"}
        ]
        if interesting:
            print(f"<details><summary><b>Updated jobs ({len(interesting)})</b></summary>\n")
            for source, detail in interesting:
                fields = ", ".join(f for f in detail.changed_fields
                                  if f not in ("description_html", "description_text"))
                print(f"- **{detail.title}** ({source}) — changed: {fields}")
            print("\n</details>\n")

    if all_reopened:
        print(f"<details><summary><b>Reopened jobs ({len(all_reopened)})</b></summary>\n")
        for source, title in all_reopened:
            print(f"- **{title}** ({source})")
        print("\n</details>\n")

    if all_closed:
        print(f"<details><summary><b>Closed jobs ({len(all_closed)})</b></summary>\n")
        for source, title in all_closed:
            print(f"- **{title}** ({source})")
        print("\n</details>\n")


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

    rows: list[SourceResult] = []

    try:
        for json_file in json_files:
            source_name = json_file.stem
            now = datetime.now(timezone.utc)

            source_jobs = load_source_jobs(json_file)
            if not source_jobs:
                logger.info("Skipping %s — no jobs", source_name)
                rows.append(SourceResult(source=source_name))
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
                missing_result = mark_missing_jobs(
                    session, source_system, set(result.seen_ids), now
                )

                sync_run.status = "success"
                sync_run.finished_at = datetime.now(timezone.utc)
                sync_run.jobs_found = len(source_jobs)
                sync_run.jobs_created = result.created
                sync_run.jobs_updated = result.updated
                sync_run.jobs_closed = missing_result.closed_count
                session.commit()

                rows.append(SourceResult(
                    source=source_system,
                    found=len(source_jobs),
                    created=result.created,
                    updated=result.updated,
                    unchanged=result.unchanged,
                    closed=missing_result.closed_count,
                    created_titles=result.created_details,
                    updated_details=result.updated_details,
                    reopened_titles=result.reopened_details,
                    closed_titles=missing_result.closed_titles,
                ))

                logger.info(
                    "%s: found=%d created=%d updated=%d unchanged=%d skipped=%d closed=%d",
                    source_system, len(source_jobs), result.created,
                    result.updated, result.unchanged, result.skipped,
                    missing_result.closed_count,
                )
            except Exception as e:
                logger.exception("Failed to upsert %s: %s", source_system, e)
                sync_run.status = "error"
                sync_run.finished_at = datetime.now(timezone.utc)
                sync_run.error_message = str(e)
                session.commit()
                rows.append(SourceResult(
                    source=source_system,
                    found=len(source_jobs),
                    error=str(e)[:60],
                ))

        print_summary(rows)

    finally:
        session.close()


if __name__ == "__main__":
    main()
