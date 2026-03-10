import json
import logging
import re
import subprocess
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from app.ingest.salary_parser import parse_salary_from_text
from app.lib.fetch_html import fetch_page
from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

# JS snippet executed inside agent-browser to extract job data from the
# rendered CSOD career-site SPA.  Returns a JSON array of objects with
# title, href, and requisitionId.
_EXTRACT_JOBS_JS = (
    "JSON.stringify(Array.from(document.querySelectorAll('a[href*=requisition]'))"
    ".map(a=>({"
    "title:a.textContent.trim(),"
    "href:a.getAttribute('href'),"
    "reqId:(a.getAttribute('href').match(/requisition\\/(\\d+)/)||[])[1]||''"
    "})))"
)

# JS snippet to extract detail fields from a CSOD requisition detail page.
_EXTRACT_DETAIL_JS = (
    "JSON.stringify({"
    "location:(document.querySelector('[data-tag=displayLocationMessage]')||{}).innerText||'',"
    "descHtml:(document.querySelector('.p-view-jobdetailsad .p-htmlviewer')||{}).innerHTML||'',"
    "descText:(document.querySelector('.p-view-jobdetailsad .p-htmlviewer')||{}).innerText||''"
    "})"
)


@dataclass(frozen=True)
class CsodConfig:
    source_system: str
    source_organization: str
    base_url: str
    career_site_id: int = 1
    site_param: str = ""

    @property
    def listing_path(self) -> str:
        path = f"/ux/ats/careersite/{self.career_site_id}/home"
        if self.site_param:
            path += f"?c={self.site_param}"
        return path


HOUSE_CAO_CONFIG = CsodConfig(
    source_system="csod-house-cao",
    source_organization="Office of the CAO",
    base_url="https://house.csodfed.com",
    career_site_id=1,
    site_param="house",
)

HOUSE_CLERK_CONFIG = CsodConfig(
    source_system="csod-house-clerk",
    source_organization="Clerk of the House",
    base_url="https://house.csodfed.com",
    career_site_id=5,
    site_param="house",
)

HOUSE_SAA_CONFIG = CsodConfig(
    source_system="csod-house-saa",
    source_organization="Sergeant at Arms",
    base_url="https://house.csodfed.com",
    career_site_id=6,
    site_param="house",
)

HOUSE_GREEN_GOLD_CONFIG = CsodConfig(
    source_system="csod-house-green-gold",
    source_organization="Green & Gold Program",
    base_url="https://house.csodfed.com",
    career_site_id=11,
    site_param="house",
)

USCP_CONFIG = CsodConfig(
    source_system="csod-uscp",
    source_organization="U.S. Capitol Police",
    base_url="https://uscp.csodfed.com",
    site_param="uscp",
)


class CsodAdapter:
    def __init__(self, config: CsodConfig):
        self.config = config
        self.source_system = config.source_system

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        """Fetch jobs using agent-browser to render the JS-driven career site."""
        jobs = self._fetch_via_browser()
        if jobs:
            logger.info("CSOD %s: found %d jobs via browser", self.config.source_system, len(jobs))
            return jobs

        logger.warning("CSOD %s: browser fetch returned no jobs, trying API fallback", self.config.source_system)
        return self._fetch_via_api(client)

    def _fetch_via_browser(self) -> list[SourceJob]:
        listing_url = f"{self.config.base_url}{self.config.listing_path}"
        try:
            # Close any stale session before starting
            subprocess.run(
                ["agent-browser", "close"],
                capture_output=True, text=True, timeout=10,
            )
            subprocess.run(
                ["agent-browser", "open", listing_url],
                capture_output=True, text=True, timeout=30, check=True,
            )
            # Wait for the SPA to render job listings
            subprocess.run(
                ["agent-browser", "wait", "a[href*=requisition]"],
                capture_output=True, text=True, timeout=15,
            )
            result = subprocess.run(
                ["agent-browser", "eval", _EXTRACT_JOBS_JS, "--json"],
                capture_output=True, text=True, timeout=15, check=True,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.exception("CSOD %s: agent-browser failed", self.config.source_system)
            subprocess.run(["agent-browser", "close"], capture_output=True, text=True, timeout=10)
            return []

        jobs = _parse_browser_result(result.stdout, self.config)
        if not jobs:
            subprocess.run(["agent-browser", "close"], capture_output=True, text=True, timeout=10)
            return jobs

        # Enrich each job by visiting its detail page (browser is still open)
        enriched: list[SourceJob] = []
        for job in jobs:
            detail = _fetch_detail_via_browser(job.source_url, self.config)
            if detail:
                enriched.append(_apply_detail(job, detail))
            else:
                enriched.append(job)

        subprocess.run(["agent-browser", "close"], capture_output=True, text=True, timeout=10)
        return enriched

    def _fetch_via_api(self, client: httpx.Client) -> list[SourceJob]:
        api_url = f"{self.config.base_url}/services/api/x/career-site/v1/search"
        try:
            resp = client.post(
                api_url,
                json={"careerSiteId": self.config.career_site_id, "pageSize": 100, "pageNumber": 1},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            return parse_api_response(data, self.config)
        except Exception:
            logger.exception("CSOD %s: API fallback also failed", self.config.source_system)
            return []


def _fetch_detail_via_browser(url: str, config: CsodConfig) -> dict | None:
    """Navigate to a detail page and extract description/location/salary."""
    try:
        subprocess.run(
            ["agent-browser", "open", url],
            capture_output=True, text=True, timeout=30, check=True,
        )
        subprocess.run(
            ["agent-browser", "wait", ".p-view-jobdetailsad .p-htmlviewer"],
            capture_output=True, text=True, timeout=20,
        )
        result = subprocess.run(
            ["agent-browser", "eval", _EXTRACT_DETAIL_JS, "--json"],
            capture_output=True, text=True, timeout=15, check=True,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.warning("CSOD %s: failed to fetch detail for %s", config.source_system, url)
        return None

    try:
        outer = json.loads(result.stdout)
        return json.loads(outer.get("data", {}).get("result", "{}"))
    except (json.JSONDecodeError, TypeError):
        return None


def _apply_detail(job: SourceJob, detail: dict) -> SourceJob:
    """Merge detail-page data into a SourceJob."""
    desc_html = detail.get("descHtml", "")
    desc_text = detail.get("descText", "")
    location = detail.get("location", "").strip() or job.location_text

    salary_min = salary_max = salary_period = None
    parsed = parse_salary_from_text(desc_text)
    if parsed:
        salary_min = parsed.min_value
        salary_max = parsed.max_value
        salary_period = parsed.period
    else:
        # CSOD often uses "Salary Range: 73,712.00 - 84,271.00" without $
        sal_match = re.search(
            r"Salary\s+Range:\s*([\d,]+(?:\.\d{2})?)\s*[-–—]\s*([\d,]+(?:\.\d{2})?)",
            desc_text,
        )
        if sal_match:
            salary_min = float(sal_match.group(1).replace(",", ""))
            salary_max = float(sal_match.group(2).replace(",", ""))
            salary_period = "hourly" if salary_min < 200 else "yearly"

    closing_at = None
    closing_match = re.search(r"Closing Date:\s*(\d{1,2}/\d{1,2}/\d{4})", desc_text)
    if closing_match:
        from datetime import datetime
        try:
            closing_at = datetime.strptime(closing_match.group(1), "%m/%d/%Y")
        except ValueError:
            pass

    return SourceJob(
        source_system=job.source_system,
        source_organization=job.source_organization,
        source_job_id=job.source_job_id,
        source_url=job.source_url,
        title=job.title,
        description_html=desc_html or job.description_html,
        description_text=desc_text or job.description_text,
        location_text=location,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_period=salary_period,
        closing_at=closing_at,
        raw_payload={**job.raw_payload, "detail": detail},
    )


def _parse_browser_result(stdout: str, config: CsodConfig) -> list[SourceJob]:
    """Parse the JSON output from agent-browser eval."""
    try:
        outer = json.loads(stdout)
        raw = outer.get("data", {}).get("result", "[]")
        items = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        logger.exception("CSOD %s: failed to parse browser output", config.source_system)
        return []

    jobs: list[SourceJob] = []
    for item in items:
        title = item.get("title", "").strip()
        if not title:
            continue
        href = item.get("href", "")
        if href and not href.startswith("http"):
            href = config.base_url + href
        req_id = item.get("reqId", "")

        jobs.append(
            SourceJob(
                source_system=config.source_system,
                source_organization=config.source_organization,
                source_job_id=req_id or None,
                source_url=href or config.base_url,
                title=title,
                description_html="",
                description_text="",
                location_text=None,
                raw_payload=item,
            )
        )
    return jobs


def parse_listing_page(html: str, config: CsodConfig) -> list[SourceJob]:
    soup = BeautifulSoup(html, "lxml")
    jobs: list[SourceJob] = []

    for card in soup.select("[data-requisition-id], .job-card, .career-job"):
        title_el = card.select_one("a, h3, .job-title")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        if href and not href.startswith("http"):
            href = config.base_url + href

        req_id = card.get("data-requisition-id", "")

        location_el = card.select_one(".location, .job-location")
        location = location_el.get_text(strip=True) if location_el else None

        jobs.append(
            SourceJob(
                source_system=config.source_system,
                source_organization=config.source_organization,
                source_job_id=req_id or None,
                source_url=href or config.base_url,
                title=title,
                description_html="",
                description_text="",
                location_text=location,
                raw_payload={"requisition_id": req_id},
            )
        )

    return jobs


def parse_api_response(data: dict, config: CsodConfig) -> list[SourceJob]:
    jobs: list[SourceJob] = []
    for item in data.get("data", data.get("results", [])):
        title = item.get("title", item.get("jobTitle", ""))
        req_id = str(item.get("requisitionId", item.get("id", "")))
        location = item.get("location", item.get("locationName", ""))
        desc = item.get("description", item.get("jobDescription", ""))
        url = item.get("applyUrl", f"{config.base_url}/ux/ats/careersite/{config.career_site_id}/home/requisition/{req_id}")

        salary_min = salary_max = salary_period = None
        parsed_salary = parse_salary_from_text(desc)
        if parsed_salary:
            salary_min = parsed_salary.min_value
            salary_max = parsed_salary.max_value
            salary_period = parsed_salary.period

        jobs.append(
            SourceJob(
                source_system=config.source_system,
                source_organization=config.source_organization,
                source_job_id=req_id or None,
                source_url=url,
                title=title,
                description_html=f"<p>{desc}</p>" if desc else "",
                description_text=desc,
                location_text=location or None,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_period=salary_period,
                raw_payload=item,
            )
        )

    return jobs
