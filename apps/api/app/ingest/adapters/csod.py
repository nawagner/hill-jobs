import json
import logging
import re
from dataclasses import dataclass

import httpx
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from app.ingest.salary_parser import parse_salary_from_text
from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

# JS snippet to extract job data from the rendered CSOD career-site SPA.
# Returns a JSON array of objects with title, href, and requisitionId.
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
        """Fetch jobs using Playwright to render the JS-driven career site."""
        listing_url = f"{self.config.base_url}{self.config.listing_path}"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                try:
                    jobs = self._scrape_listing(page, listing_url)
                    if not jobs:
                        logger.warning("CSOD %s: no jobs found", self.config.source_system)
                        return []

                    logger.info("CSOD %s: found %d jobs via Playwright", self.config.source_system, len(jobs))

                    enriched: list[SourceJob] = []
                    for job in jobs:
                        detail = _fetch_detail(page, job.source_url, self.config)
                        if detail:
                            enriched.append(_apply_detail(job, detail))
                        else:
                            enriched.append(job)
                    return enriched
                finally:
                    browser.close()
        except Exception:
            logger.exception("CSOD %s: Playwright scrape failed", self.config.source_system)
            return []

    def _scrape_listing(self, page, listing_url: str) -> list[SourceJob]:
        page.goto(listing_url, wait_until="domcontentloaded")
        try:
            page.wait_for_selector("a[href*=requisition]", timeout=15000)
        except PlaywrightTimeout:
            logger.warning("CSOD %s: timed out waiting for job links", self.config.source_system)
            return []

        raw = page.evaluate(_EXTRACT_JOBS_JS)
        items = json.loads(raw) if isinstance(raw, str) else raw

        jobs: list[SourceJob] = []
        for item in items:
            title = item.get("title", "").strip()
            if not title:
                continue
            href = item.get("href", "")
            if href and not href.startswith("http"):
                href = self.config.base_url + href
            req_id = item.get("reqId", "")

            jobs.append(
                SourceJob(
                    source_system=self.config.source_system,
                    source_organization=self.config.source_organization,
                    source_job_id=req_id or None,
                    source_url=href or self.config.base_url,
                    title=title,
                    description_html="",
                    description_text="",
                    location_text=None,
                    raw_payload=item,
                )
            )
        return jobs


def _fetch_detail(page, url: str, config: CsodConfig) -> dict | None:
    """Navigate to a detail page and extract description/location/salary."""
    try:
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_selector(".p-view-jobdetailsad .p-htmlviewer", timeout=15000)
    except PlaywrightTimeout:
        logger.warning("CSOD %s: timed out loading detail for %s", config.source_system, url)
        return None
    except Exception:
        logger.warning("CSOD %s: failed to fetch detail for %s", config.source_system, url)
        return None

    try:
        raw = page.evaluate(_EXTRACT_DETAIL_JS)
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        logger.warning("CSOD %s: failed to parse detail for %s", config.source_system, url)
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
