import importlib.util
from pathlib import Path

import pytest

from app.ingest.run_all import SyncRunResult

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "cron_ingest.py"
_spec = importlib.util.spec_from_file_location("cron_ingest", _SCRIPT)
cron_ingest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cron_ingest)


def _failed(results: dict[str, SyncRunResult]) -> list[str]:
    return cron_ingest.failed_sources(results)


def test_error_is_a_failure():
    results = {"senate-webscribble": SyncRunResult(status="error", error="boom")}
    assert _failed(results) == ["senate-webscribble"]


def test_error_is_a_failure_even_for_allow_empty_source():
    results = {"aoc-usajobs": SyncRunResult(status="error", error="401")}
    assert _failed(results) == ["aoc-usajobs"]


def test_empty_source_not_in_allow_empty_is_a_failure():
    results = {
        "loc-careers": SyncRunResult(status="empty"),
        "csod-house-clerk": SyncRunResult(status="empty"),
    }
    assert _failed(results) == ["loc-careers", "csod-house-clerk"]


def test_empty_source_in_allow_empty_is_not_a_failure():
    results = {
        "aoc-usajobs": SyncRunResult(status="empty"),
        "house-hvaps": SyncRunResult(status="empty"),
    }
    assert _failed(results) == []


def test_empty_house_saa_is_now_a_failure():
    # CSOD reports a confirmed-empty site as "success"; "empty" no longer
    # happens for it, so it isn't excused any more.
    assert "csod-house-saa" not in cron_ingest.ALLOW_EMPTY
    assert _failed({"csod-house-saa": SyncRunResult(status="empty")}) == ["csod-house-saa"]


@pytest.mark.parametrize(
    "name",
    ["csod-house-clerk", "csod-house-saa", "senate-webscribble", "aoc-usajobs"],
)
def test_success_with_zero_jobs_is_not_a_failure(name):
    assert _failed({name: SyncRunResult(status="success", jobs_found=0)}) == []


def test_failures_are_listed_in_registry_order():
    results = {
        "senate-webscribble": SyncRunResult(status="success", jobs_found=12),
        "loc-careers": SyncRunResult(status="error", error="cloudflare"),
        "aoc-usajobs": SyncRunResult(status="empty"),
        "csod-house-cao": SyncRunResult(status="empty"),
        "csod-house-clerk": SyncRunResult(status="success", jobs_found=0),
        "csod-house-saa": SyncRunResult(status="error", error="no search response"),
        "csod-uscp": SyncRunResult(status="success", jobs_found=9),
    }
    assert _failed(results) == ["loc-careers", "csod-house-cao", "csod-house-saa"]


class _FakeEngine:
    def dispose(self):
        pass


class _FakeSession:
    def close(self):
        pass


def _patch_main(monkeypatch, results: dict[str, SyncRunResult]) -> None:
    """Run main() without settings, a database or any sources."""
    monkeypatch.setattr(cron_ingest, "Settings", lambda: None)
    monkeypatch.setattr(cron_ingest, "get_engine", _FakeEngine)
    monkeypatch.setattr(cron_ingest, "sessionmaker", lambda **kwargs: _FakeSession)
    monkeypatch.setattr(cron_ingest, "build_registry", lambda settings: {})
    monkeypatch.setattr(cron_ingest, "run_all_sources", lambda session, registry, client: results)


def test_main_exits_nonzero_when_house_saa_is_empty(monkeypatch):
    _patch_main(
        monkeypatch,
        {
            "senate-webscribble": SyncRunResult(status="success", jobs_found=12),
            "csod-house-clerk": SyncRunResult(status="success", jobs_found=0),
            "csod-house-saa": SyncRunResult(status="empty"),
        },
    )
    with pytest.raises(SystemExit) as excinfo:
        cron_ingest.main()
    assert excinfo.value.code == 1
