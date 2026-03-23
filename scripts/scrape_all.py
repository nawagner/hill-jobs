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
from app.ingest.adapters.cbo_bizmerlin import CboBizmerlinAdapter
from app.ingest.adapters.usajobs import UsajobsAdapter, GAO_CONFIG, GPO_CONFIG
from app.ingest.adapters.csod import (
    CsodAdapter,
    HOUSE_CAO_CONFIG,
    HOUSE_CLERK_CONFIG,
    HOUSE_SAA_CONFIG,
    HOUSE_GREEN_GOLD_CONFIG,
    USCP_CONFIG,
)
from app.ingest.adapters.hvaps_email import HvapsEmailAdapter

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def job_to_dict(job) -> dict:
    """Convert a SourceJob to a JSON-serializable dict."""
    return job.model_dump(mode="json")


def print_detail(name: str, jobs: list[dict]):
    """Print sample jobs for a source."""
    if not jobs:
        return

    print(f"\n<details><summary><b>{name}</b> — {len(jobs)} jobs</summary>\n")
    for job in jobs[:5]:
        salary = ""
        if job.get("salary_min") and job.get("salary_max"):
            salary = f" | ${job['salary_min']:,.0f}-${job['salary_max']:,.0f} {job.get('salary_period', '')}"
        location = f" | {job['location_text']}" if job.get("location_text") else ""
        print(f"- **{job['title']}** — {job.get('source_organization', 'N/A')}{location}{salary}")
    if len(jobs) > 5:
        print(f"- _...and {len(jobs) - 5} more_")
    print("\n</details>")


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
        ("gao_usajobs", UsajobsAdapter(GAO_CONFIG, api_key=usajobs_api_key, user_agent_email=usajobs_email)),
        ("gpo_usajobs", UsajobsAdapter(GPO_CONFIG, api_key=usajobs_api_key, user_agent_email=usajobs_email)),
        ("cbo_bizmerlin", CboBizmerlinAdapter()),
        ("csod_house_cao", CsodAdapter(HOUSE_CAO_CONFIG)),
        ("csod_house_clerk", CsodAdapter(HOUSE_CLERK_CONFIG)),
        ("csod_house_saa", CsodAdapter(HOUSE_SAA_CONFIG)),
        ("csod_house_green_gold", CsodAdapter(HOUSE_GREEN_GOLD_CONFIG)),
        ("csod_uscp", CsodAdapter(USCP_CONFIG)),
        ("hvaps", HvapsEmailAdapter()),
    ]

    # Sources that may legitimately have 0 jobs
    # csod_house_saa: no current openings
    # aoc_usajobs: skipped if no API key configured
    # hvaps: skipped if no GMAIL_APP_PASSWORD configured
    allow_empty = {"csod_house_saa", "aoc_usajobs", "gao_usajobs", "gpo_usajobs", "cbo_bizmerlin", "hvaps"}

    total = 0
    all_results: dict[str, list[dict]] = {}
    statuses: list[dict] = []  # for the summary table
    failures = []

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    with httpx.Client(timeout=60.0) as client:
        for name, adapter in adapters:
            try:
                raw_jobs = adapter.fetch_jobs(client)
                jobs = [job_to_dict(j) for j in raw_jobs]
            except Exception as e:
                logger.exception("Failed to scrape %s", name)
                jobs = []
                if name in allow_empty:
                    statuses.append({"name": name, "count": 0, "status": "SKIP", "note": f"error (allowed): {e!s:.50}"})
                else:
                    failures.append(f"{name}: exception — {e}")
                    statuses.append({"name": name, "count": 0, "status": "FAIL", "note": str(e)[:60]})
                continue

            all_results[name] = jobs
            total += len(jobs)

            # Save individual source file
            out_file = output_dir / f"{name}.json"
            out_file.write_text(json.dumps(jobs, indent=2, default=str))

            if not jobs and name not in allow_empty:
                failures.append(f"{name}: returned 0 jobs (site may have changed)")
                statuses.append({"name": name, "count": 0, "status": "WARN", "note": "0 jobs — site may have changed"})
            elif not jobs:
                statuses.append({"name": name, "count": 0, "status": "SKIP", "note": "allowed empty / no credentials"})
            else:
                statuses.append({"name": name, "count": len(jobs), "status": "OK", "note": ""})

    # Save combined file
    combined_file = output_dir / "all_jobs.json"
    all_jobs = []
    for jobs in all_results.values():
        all_jobs.extend(jobs)
    combined_file.write_text(json.dumps(all_jobs, indent=2, default=str))

    # ── Print summary ──────────────────────────────────────────────────
    print(f"# Scrape Results — {timestamp}\n")

    # Status table
    print("| Source | Status | Jobs | Note |")
    print("|--------|--------|------|------|")
    for s in statuses:
        icon = {"OK": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "⏭️"}[s["status"]]
        print(f"| {s['name']} | {icon} {s['status']} | {s['count']} | {s['note']} |")

    ok_count = sum(1 for s in statuses if s["status"] == "OK")
    fail_count = sum(1 for s in statuses if s["status"] in ("FAIL", "WARN"))
    print(f"\n**{total} jobs from {ok_count} sources** ({fail_count} failed/warning)")
    print(f"Files saved to `{output_dir}/`")

    # Expandable details per source
    print("\n---\n## Details\n")
    for name, jobs in all_results.items():
        print_detail(name, jobs)

    if failures:
        print("\n## ❌ Failures\n")
        for f in failures:
            print(f"- {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
