#!/usr/bin/env python3
"""Scrape all sources, save as JSON, print summary.

Usage:
  python scripts/scrape_all.py [--output-dir data/scraped]
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Load .env from repo root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from app.ingest.adapters.senate import SenateAdapter
from app.ingest.adapters.loc import LocAdapter
from app.ingest.adapters.house_dems_resumebank import HouseDemsResumebankAdapter
from app.ingest.adapters.aoc_usajobs import AocUsajobsAdapter
from app.ingest.adapters.csod import (
    CsodAdapter,
    HOUSE_CAO_CONFIG,
    HOUSE_CLERK_CONFIG,
    HOUSE_SAA_CONFIG,
    HOUSE_GREEN_GOLD_CONFIG,
    USCP_CONFIG,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def job_to_dict(job) -> dict:
    """Convert a SourceJob to a JSON-serializable dict."""
    d = {}
    for field in [
        "source_system", "source_organization", "source_job_id", "source_url",
        "title", "description_text", "location_text", "employment_type",
        "salary_min", "salary_max", "salary_period",
    ]:
        d[field] = getattr(job, field, None)
    for field in ["posted_at", "closing_at"]:
        val = getattr(job, field, None)
        d[field] = val.isoformat() if val else None
    return d


def print_summary(name: str, jobs: list[dict]):
    """Print a markdown-friendly summary for a source."""
    print(f"\n### {name}: {len(jobs)} jobs found")
    if not jobs:
        print("_(no jobs)_")
        return

    # Show first 3 examples
    for job in jobs[:3]:
        salary = ""
        if job.get("salary_min") and job.get("salary_max"):
            salary = f" | ${job['salary_min']:,.0f}-${job['salary_max']:,.0f} {job.get('salary_period', '')}"
        location = f" | {job['location_text']}" if job.get("location_text") else ""
        print(f"- **{job['title']}** — {job.get('source_organization', 'N/A')}{location}{salary}")

    if len(jobs) > 3:
        print(f"- _...and {len(jobs) - 3} more_")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="data/scraped")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    usajobs_api_key = os.environ.get("USAJOBS_API_KEY", "")
    usajobs_email = os.environ.get("USAJOBS_USER_AGENT_EMAIL", "")

    adapters = [
        ("senate", SenateAdapter()),
        ("loc", LocAdapter()),
        ("house_dems_resumebank", HouseDemsResumebankAdapter()),
        ("aoc_usajobs", AocUsajobsAdapter(api_key=usajobs_api_key, user_agent_email=usajobs_email)),
        ("csod_house_cao", CsodAdapter(HOUSE_CAO_CONFIG)),
        ("csod_house_clerk", CsodAdapter(HOUSE_CLERK_CONFIG)),
        ("csod_house_saa", CsodAdapter(HOUSE_SAA_CONFIG)),
        ("csod_house_green_gold", CsodAdapter(HOUSE_GREEN_GOLD_CONFIG)),
        ("csod_uscp", CsodAdapter(USCP_CONFIG)),
    ]

    # Sources that may legitimately have 0 jobs
    # csod_house_saa: no current openings
    # aoc_usajobs: skipped if no API key configured
    allow_empty = {"csod_house_saa", "aoc_usajobs"}

    total = 0
    all_results = {}
    failures = []

    print(f"# Scrape Results — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    with httpx.Client(timeout=60.0) as client:
        for name, adapter in adapters:
            try:
                raw_jobs = adapter.fetch_jobs(client)
                jobs = [job_to_dict(j) for j in raw_jobs]
            except Exception as e:
                logger.exception("Failed to scrape %s", name)
                jobs = []
                failures.append(f"{name}: exception — {e}")
                print(f"\n### {name}: FAILED ({e})")
                continue

            if not jobs and name not in allow_empty:
                failures.append(f"{name}: returned 0 jobs (site may have changed)")

            all_results[name] = jobs
            total += len(jobs)

            # Save individual source file
            out_file = output_dir / f"{name}.json"
            out_file.write_text(json.dumps(jobs, indent=2, default=str))

            print_summary(name, jobs)

    # Save combined file
    combined_file = output_dir / "all_jobs.json"
    all_jobs = []
    for jobs in all_results.values():
        all_jobs.extend(jobs)
    combined_file.write_text(json.dumps(all_jobs, indent=2, default=str))

    print(f"\n---\n**Total: {total} jobs across {len(all_results)} sources**")
    print(f"Files saved to `{output_dir}/`")

    if failures:
        print("\n## Failures")
        for f in failures:
            print(f"- {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
