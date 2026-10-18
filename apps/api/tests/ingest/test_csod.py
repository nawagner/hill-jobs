import json
import logging
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from playwright.sync_api import Error as PlaywrightError

from app.ingest.adapters import csod
from app.ingest.adapters.csod import (
    CsodAdapter,
    CsodConfig,
    HOUSE_CAO_CONFIG,
    HOUSE_CLERK_CONFIG,
    HOUSE_GREEN_GOLD_CONFIG,
    HOUSE_SAA_CONFIG,
    _apply_detail,
)
from app.schemas.ingest import SourceJob


TEST_CONFIG = CsodConfig(
    source_system="csod-test",
    source_organization="Test Org",
    base_url="https://test.csod.com",
)


def test_house_csod_configs():
    assert HOUSE_CAO_CONFIG.career_site_id == 1
    assert HOUSE_CAO_CONFIG.listing_path == "/ux/ats/careersite/1/home?c=house"

    assert HOUSE_CLERK_CONFIG.career_site_id == 5
    assert HOUSE_CLERK_CONFIG.listing_path == "/ux/ats/careersite/5/home?c=house"

    assert HOUSE_SAA_CONFIG.career_site_id == 6
    assert HOUSE_SAA_CONFIG.listing_path == "/ux/ats/careersite/6/home?c=house"

    assert HOUSE_GREEN_GOLD_CONFIG.career_site_id == 11
    assert HOUSE_GREEN_GOLD_CONFIG.listing_path == "/ux/ats/careersite/11/home?c=house"


def test_apply_detail_enriches_job():
    job = SourceJob(
        source_system="csod-test",
        source_organization="Test Org",
        source_job_id="123",
        source_url="https://test.csod.com/requisition/123",
        title="Test Job",
        description_html="",
        description_text="",
        raw_payload={},
    )
    detail = {
        "location": "WASHINGTON, DC, United States",
        "descHtml": "<p><strong>Salary Range:</strong> 73,712.00 - 84,271.00</p><p>Closing Date: 3/23/2026</p><p>Job description here</p>",
        "descText": "Salary Range: 73,712.00 - 84,271.00\nClosing Date: 3/23/2026\nJob description here",
    }
    enriched = _apply_detail(job, detail)
    assert enriched.location_text == "WASHINGTON, DC, United States"
    assert enriched.description_text == detail["descText"]
    assert enriched.description_html == detail["descHtml"]
    assert enriched.salary_min == 73712.0
    assert enriched.salary_max == 84271.0
    assert enriched.salary_period == "yearly"
    assert enriched.closing_at is not None
    assert enriched.closing_at.month == 3
    assert enriched.closing_at.day == 23


# ── _jobs_from_listing ──────────────────────────────────────────────────


def _search_body(total_count) -> dict:
    """A rec-job-search/external/jobs response body, as the CSOD SPA receives it."""
    return {
        "status": "Success",
        "timestamp": "2026-10-18T10:00:00Z",
        "data": {
            "totalCount": total_count,
            "requisitions": [],
            "filters": [],
            "customFieldFilters": [],
        },
    }


def _item(title: str, href: str, req_id: str = "") -> dict:
    """One link as _EXTRACT_JOBS_JS returns it."""
    return {"title": title, "href": href, "reqId": req_id}


ONE_ITEM = [_item("Staff Assistant", "/ux/ats/careersite/5/home/requisition/101?c=house", "101")]


def test_scrape_error_is_an_exception():
    # run_all_sources records an adapter's Exception as a failed source.
    assert issubclass(csod.CsodScrapeError, Exception)


@pytest.mark.parametrize("items", [[], ONE_ITEM], ids=["no-links", "links"])
@pytest.mark.parametrize(
    "search_body",
    [
        None,
        {},
        {"status": "Success", "data": None},
        {"status": "Success", "data": {}},
        {"data": {"totalCount": None}},
        {"data": {"totalCount": "4"}},
        {"data": {"totalCount": 4.0}},
        {"data": {"totalCount": True}},
        {"data": {"totalCount": False}},
        {"data": {"totalCount": -1}},
    ],
    ids=[
        "no-response",
        "no-data",
        "data-null",
        "no-total-count",
        "total-count-null",
        "total-count-string",
        "total-count-float",
        "total-count-true",
        "total-count-false",
        "total-count-negative",
    ],
)
def test_jobs_from_listing_without_valid_total_count_raises(search_body, items):
    with pytest.raises(csod.CsodScrapeError):
        csod._jobs_from_listing(TEST_CONFIG, search_body, items)


def test_jobs_from_listing_confirmed_empty_returns_no_jobs():
    assert csod._jobs_from_listing(TEST_CONFIG, _search_body(0), []) == []


def test_jobs_from_listing_confirmed_empty_ignores_links():
    # The job-search API is authoritative: a zero count means no openings,
    # even if something on the page happens to match the link selector.
    assert csod._jobs_from_listing(TEST_CONFIG, _search_body(0), ONE_ITEM) == []


def test_jobs_from_listing_count_without_links_raises_with_count():
    with pytest.raises(csod.CsodScrapeError) as excinfo:
        csod._jobs_from_listing(TEST_CONFIG, _search_body(37), [])
    assert "37" in str(excinfo.value)


def test_jobs_from_listing_count_with_only_blank_titles_raises_with_count():
    # [] from this adapter means "no openings" and closes stale jobs, so a
    # positive count that yields no jobs must be an error, not [].
    items = [
        _item("", "/ux/ats/careersite/5/home/requisition/101?c=house", "101"),
        _item("   ", "/ux/ats/careersite/5/home/requisition/102?c=house", "102"),
    ]
    with pytest.raises(csod.CsodScrapeError) as excinfo:
        csod._jobs_from_listing(TEST_CONFIG, _search_body(37), items)
    assert "37" in str(excinfo.value)


def test_jobs_from_listing_builds_source_jobs_from_links():
    items = [
        _item("  Staff Assistant  ", "/ux/ats/careersite/5/home/requisition/101?c=house", "101"),
        _item("   ", "/ux/ats/careersite/5/home/requisition/102?c=house", "102"),
        _item("Systems Engineer", "https://other.csod.com/requisition/103", ""),
        _item("Records Clerk", "", ""),
    ]
    jobs = csod._jobs_from_listing(TEST_CONFIG, _search_body(len(items)), items)

    assert [j.title for j in jobs] == ["Staff Assistant", "Systems Engineer", "Records Clerk"]
    assert [j.source_url for j in jobs] == [
        "https://test.csod.com/ux/ats/careersite/5/home/requisition/101?c=house",
        "https://other.csod.com/requisition/103",
        "https://test.csod.com",
    ]
    assert [j.source_job_id for j in jobs] == ["101", None, None]
    assert [j.raw_payload for j in jobs] == [items[0], items[2], items[3]]
    for job in jobs:
        assert isinstance(job, SourceJob)
        assert job.source_system == "csod-test"
        assert job.source_organization == "Test Org"
        assert job.description_html == ""
        assert job.description_text == ""
        assert job.location_text is None


def test_jobs_from_listing_count_above_rendered_links_is_not_an_error():
    # The listing shows 25 jobs per page; pagination is handled separately.
    items = [_item(f"Fellow {n}", f"/requisition/{n}", str(n)) for n in range(25)]
    jobs = csod._jobs_from_listing(TEST_CONFIG, _search_body(33), items)
    assert len(jobs) == 25


# ── CsodAdapter.fetch_jobs (fake browser, no network) ───────────────────


class _FakePage:
    """Stands in for a Playwright page on CSOD detail pages."""

    def __init__(self, details: dict[str, dict] | None = None, fail_urls: set[str] = frozenset()):
        self.details = details or {}
        self.fail_urls = fail_urls
        self.url = "about:blank"

    def goto(self, url, **kwargs):
        if url in self.fail_urls:
            raise PlaywrightError(f"net::ERR_CONNECTION_RESET at {url}")
        self.url = url

    def wait_for_selector(self, selector, **kwargs):
        return None

    def evaluate(self, script):
        return json.dumps(self.details[self.url])


class _FakeBrowser:
    def __init__(self, page: _FakePage):
        self.page = page

    def new_page(self):
        return self.page

    def close(self):
        pass


def _use_fake_browser(monkeypatch, page: _FakePage | None = None) -> None:
    """Replace sync_playwright in the csod module so no real browser launches."""
    browser = _FakeBrowser(page or _FakePage())

    @contextmanager
    def fake_sync_playwright():
        yield SimpleNamespace(chromium=SimpleNamespace(launch=lambda **kwargs: browser))

    monkeypatch.setattr(csod, "sync_playwright", fake_sync_playwright)


def _use_listing(monkeypatch, search_body, items):
    """Make the listing page 'load' with this job-search response and these links."""
    loaded: list[str] = []

    def fake_load_listing(page, listing_url):
        loaded.append(listing_url)
        return search_body, items

    monkeypatch.setattr(csod, "_load_listing", fake_load_listing)
    return loaded


def test_empty_is_authoritative():
    assert getattr(CsodAdapter, "empty_is_authoritative", None) is True


def test_fetch_jobs_confirmed_empty_site_returns_no_jobs(monkeypatch):
    _use_fake_browser(monkeypatch)
    loaded = _use_listing(monkeypatch, _search_body(0), [])

    assert CsodAdapter(HOUSE_CLERK_CONFIG).fetch_jobs(None) == []
    assert loaded == ["https://house.csodfed.com/ux/ats/careersite/5/home?c=house"]


def test_fetch_jobs_confirmed_empty_site_does_not_warn(monkeypatch, caplog):
    _use_fake_browser(monkeypatch)
    _use_listing(monkeypatch, _search_body(0), [])

    with caplog.at_level(logging.DEBUG, logger=csod.__name__):
        CsodAdapter(HOUSE_CLERK_CONFIG).fetch_jobs(None)

    assert [r for r in caplog.records if r.levelno >= logging.WARNING] == []


@pytest.mark.parametrize(
    "search_body",
    [None, _search_body(4)],
    ids=["no-search-response", "count-without-links"],
)
def test_fetch_jobs_raises_when_listing_cannot_be_confirmed(monkeypatch, search_body):
    _use_fake_browser(monkeypatch)
    _use_listing(monkeypatch, search_body, [])

    with pytest.raises(csod.CsodScrapeError):
        CsodAdapter(HOUSE_CLERK_CONFIG).fetch_jobs(None)


def test_fetch_jobs_propagates_playwright_errors(monkeypatch):
    _use_fake_browser(monkeypatch)

    def broken_load_listing(page, listing_url):
        raise PlaywrightError("net::ERR_NAME_NOT_RESOLVED")

    monkeypatch.setattr(csod, "_load_listing", broken_load_listing)

    with pytest.raises(PlaywrightError):
        CsodAdapter(HOUSE_CLERK_CONFIG).fetch_jobs(None)


def test_fetch_jobs_enrichment_failure_on_one_job_keeps_the_others(monkeypatch):
    first = "https://house.csodfed.com/ux/ats/careersite/1/home/requisition/201?c=house"
    second = "https://house.csodfed.com/ux/ats/careersite/1/home/requisition/202?c=house"
    page = _FakePage(
        details={
            second: {
                "location": "WASHINGTON, DC, United States",
                "descHtml": "<p>Supports the Office.</p>",
                "descText": "Supports the Office.",
            }
        },
        fail_urls={first},
    )
    _use_fake_browser(monkeypatch, page)
    _use_listing(
        monkeypatch,
        _search_body(2),
        [
            _item("Payroll Specialist", "/ux/ats/careersite/1/home/requisition/201?c=house", "201"),
            _item("Help Desk Analyst", "/ux/ats/careersite/1/home/requisition/202?c=house", "202"),
        ],
    )

    jobs = CsodAdapter(HOUSE_CAO_CONFIG).fetch_jobs(None)

    assert [j.source_job_id for j in jobs] == ["201", "202"]
    assert jobs[0].description_text == ""
    assert jobs[1].description_text == "Supports the Office."
    assert jobs[1].location_text == "WASHINGTON, DC, United States"
