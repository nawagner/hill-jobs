import logging
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from app.lib.fetch_html import fetch_page
from app.schemas.ingest import SourceJob

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CsodConfig:
    source_system: str
    source_organization: str
    base_url: str
    listing_path: str = "/ux/ats/careersite/1/home"


HOUSE_CAO_CONFIG = CsodConfig(
    source_system="csod-house-cao",
    source_organization="House CAO",
    base_url="https://house.csod.com",
)

USCP_CONFIG = CsodConfig(
    source_system="csod-uscp",
    source_organization="U.S. Capitol Police",
    base_url="https://uscp.csod.com",
)


class CsodAdapter:
    def __init__(self, config: CsodConfig):
        self.config = config
        self.source_system = config.source_system

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        listing_url = f"{self.config.base_url}{self.config.listing_path}"
        try:
            html = fetch_page(client, listing_url)
        except httpx.HTTPStatusError:
            logger.warning(
                "CSOD %s: listing page returned error, trying API fallback",
                self.config.source_system,
            )
            return self._fetch_via_api(client)

        jobs = parse_listing_page(html, self.config)
        if not jobs:
            logger.info(
                "CSOD %s: HTML listing empty, trying API fallback",
                self.config.source_system,
            )
            return self._fetch_via_api(client)

        logger.info("CSOD %s: found %d jobs", self.config.source_system, len(jobs))
        return jobs

    def _fetch_via_api(self, client: httpx.Client) -> list[SourceJob]:
        api_url = f"{self.config.base_url}/services/api/x/career-site/v1/search"
        try:
            resp = client.post(
                api_url,
                json={"careerSiteId": 1, "pageSize": 100, "pageNumber": 1},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            return parse_api_response(data, self.config)
        except Exception:
            logger.exception("CSOD %s: API fallback also failed", self.config.source_system)
            return []


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
        url = item.get("applyUrl", f"{config.base_url}/ux/ats/careersite/1/home/requisition/{req_id}")

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
                raw_payload=item,
            )
        )

    return jobs
