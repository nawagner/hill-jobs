import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from playwright.sync_api import Error as PlaywrightError, sync_playwright, TimeoutError as PlaywrightTimeout

from app.ingest.salary_parser import parse_salary_from_text
from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)

# The career-site SPA POSTs to this API to list jobs; its response's
# data.totalCount says how many openings the site has, and data.requisitions
# holds one page of them (25 by default).
_JOB_SEARCH_PATH = "rec-job-search/external/jobs"
# Headers the SPA sends that a replayed job-search request needs (auth included).
_REPLAY_HEADERS = {"authorization", "content-type", "accept", "csod-accept-language"}
# Upper bound on job-search pages read per site (25 jobs each).
_MAX_PAGES = 40

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


class CsodScrapeError(Exception):
    """The listing page didn't confirm how many jobs the site has, or its job links didn't load."""


class CsodAdapter:
    # [] means the site's job search confirmed zero openings; failures raise.
    empty_is_authoritative = True

    def __init__(self, config: CsodConfig):
        self.config = config
        self.source_system = config.source_system

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        """Fetch jobs using Playwright to render the JS-driven career site.

        Returns [] only when the site's job search reports zero openings.
        Raises CsodScrapeError or a Playwright error when the listing can't be read.
        """
        listing_url = f"{self.config.base_url}{self.config.listing_path}"
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                jobs = self._scrape_listing(page, listing_url)
                if not jobs:
                    logger.info("CSOD %s: no current openings", self.config.source_system)
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

    def _scrape_listing(self, page, listing_url: str) -> list[SourceJob]:
        return _jobs_from_listing(self.config, *_load_listing(page, listing_url))


def _total_count(search_body) -> int | None:
    """data.totalCount from a job-search response body, or None if missing or invalid."""
    data = search_body.get("data") if isinstance(search_body, dict) else None
    total = data.get("totalCount") if isinstance(data, dict) else None
    if isinstance(total, bool) or not isinstance(total, int) or total < 0:
        return None
    return total


def _jobs_from_listing(
    config: CsodConfig, search_body: dict | None, items: list[dict]
) -> list[SourceJob]:
    """Build jobs from the listing's links, checked against the job-search count.

    Returns [] only when the job search reports zero openings, because callers
    trust that [] and close the source's stale jobs. Anything else that yields
    no jobs raises CsodScrapeError.
    """
    total = _total_count(search_body)
    if total is None:
        raise CsodScrapeError(
            f"CSOD {config.source_system}: no valid totalCount in the job-search response"
        )
    if total == 0:
        return []
    # A partial read would let mark_missing_jobs close the jobs it left out.
    if len(items) < total:
        raise CsodScrapeError(
            f"CSOD {config.source_system}: job search reports {total} openings "
            f"but only {len(items)} were read"
        )

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

    if not jobs:
        raise CsodScrapeError(
            f"CSOD {config.source_system}: job search reports {total} openings "
            "but none had a title"
        )
    return jobs


def _collect_requisitions(first_body: dict, fetch_page) -> list[dict]:
    """Every requisition across the job search's pages, without repeats.

    `first_body` is the page-1 response; `fetch_page(n)` returns the response
    body for page n, or None if it couldn't be read. Stops once the reported
    totalCount is reached, when a page fails or comes back empty, or after
    _MAX_PAGES pages. The caller checks the result against totalCount.
    """
    total = _total_count(first_body) or 0
    requisitions: list[dict] = []
    seen: set = set()

    def add(page_body) -> int:
        data = page_body.get("data") if isinstance(page_body, dict) else None
        page_reqs = data.get("requisitions") if isinstance(data, dict) else None
        added = 0
        for req in page_reqs if isinstance(page_reqs, list) else []:
            req_id = req.get("requisitionId") if isinstance(req, dict) else None
            if req_id is None or req_id in seen:
                continue
            seen.add(req_id)
            requisitions.append(req)
            added += 1
        return added

    add(first_body)
    page_number = 1
    while len(requisitions) < total and page_number < _MAX_PAGES:
        page_number += 1
        page_body = fetch_page(page_number)
        data = page_body.get("data") if isinstance(page_body, dict) else None
        if not isinstance(data, dict) or not data.get("requisitions"):
            break
        add(page_body)
    return requisitions


def _items_from_requisitions(listing_url: str, requisitions: list[dict]) -> list[dict]:
    """Job items ({title, href, reqId}) as the listing page links them.

    The page links each job at <listing path>/requisition/<id>?<listing query>,
    e.g. /ux/ats/careersite/11/home/requisition/5667?c=house.
    """
    parts = urlsplit(listing_url)
    query = f"?{parts.query}" if parts.query else ""
    items = []
    for req in requisitions:
        req_id = req.get("requisitionId")
        items.append({
            "title": (req.get("displayJobTitle") or "").strip(),
            "href": f"{parts.path}/requisition/{req_id}{query}",
            "reqId": str(req_id) if req_id is not None else "",
        })
    return items


def _is_job_search_response(response) -> bool:
    return response.request.method == "POST" and _JOB_SEARCH_PATH in response.url


def _load_listing(page, listing_url: str) -> tuple[dict | None, list[dict]]:
    """Open a career-site listing; return (job-search response body, job items).

    The body is the parsed JSON the SPA gets from its job-search API, or None if
    that response never came, wasn't a 200 or wasn't JSON. When it reports
    openings, the remaining pages are read by replaying the SPA's own request
    with the next page number, and every job becomes an item. Navigation errors
    propagate.
    """
    label = re.sub(r"[^A-Za-z0-9]+", "-", listing_url.split("://", 1)[-1]).strip("-")
    body = None
    navigated = False
    try:
        with page.expect_response(_is_job_search_response, timeout=30000) as response_info:
            page.goto(listing_url, wait_until="domcontentloaded")
            navigated = True
        response = response_info.value
    except PlaywrightTimeout:
        if not navigated:
            raise
        logger.warning("CSOD %s: timed out waiting for the job-search response", listing_url)
    else:
        if response.status != 200:
            logger.warning("CSOD %s: job-search response status %d", listing_url, response.status)
        else:
            try:
                body = response.json()
            except ValueError:
                logger.warning("CSOD %s: job-search response is not JSON", listing_url)

    total = _total_count(body)
    if total is None:
        _dump_debug_artifacts(page, label, "no-job-count")
        return body, []
    if total == 0:
        return body, []

    request = response.request
    try:
        request_body = json.loads(request.post_data or "{}")
    except ValueError:
        request_body = {}
    headers = {k: v for k, v in request.headers.items() if k.lower() in _REPLAY_HEADERS}

    def fetch_page(page_number: int) -> dict | None:
        try:
            replay = page.request.post(
                response.url,
                headers=headers,
                data=json.dumps({**request_body, "pageNumber": page_number}),
                timeout=30000,
            )
            if not replay.ok:
                logger.warning(
                    "CSOD %s: job-search page %d status %d", listing_url, page_number, replay.status
                )
                return None
            return replay.json()
        except (PlaywrightError, ValueError):
            logger.warning("CSOD %s: couldn't read job-search page %d", listing_url, page_number)
            return None

    requisitions = _collect_requisitions(body, fetch_page)
    if len(requisitions) < total:
        logger.warning(
            "CSOD %s: read %d of %d jobs from the job search", listing_url, len(requisitions), total
        )
        _dump_debug_artifacts(page, label, "partial-listing")
    return body, _items_from_requisitions(listing_url, requisitions)


def _dump_debug_artifacts(page, source_system: str, tag: str) -> None:
    debug_dir = os.environ.get("CSOD_DEBUG_DIR")
    if not debug_dir:
        return
    try:
        out = Path(debug_dir)
        out.mkdir(parents=True, exist_ok=True)
        stem = f"{source_system}-{tag}"
        page.screenshot(path=str(out / f"{stem}.png"), full_page=True)
        (out / f"{stem}.html").write_text(page.content(), encoding="utf-8")
        (out / f"{stem}.url.txt").write_text(page.url, encoding="utf-8")
        logger.info("CSOD %s: dumped debug artifacts to %s", source_system, out)
    except Exception:
        logger.exception("CSOD %s: failed to dump debug artifacts", source_system)


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
