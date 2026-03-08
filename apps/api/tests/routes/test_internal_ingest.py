from unittest.mock import patch

import httpx

from app.config import Settings
from app.schemas.ingest import SourceJob


def _mock_settings():
    return Settings(
        database_url="sqlite:///:memory:",
        internal_ingest_token="test-token-123",
        usajobs_api_key=None,
    )


class _StubAdapter:
    source_system = "stub"

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]:
        return [
            SourceJob(
                source_system="stub",
                source_organization="Stub Org",
                source_job_id="S1",
                source_url="https://example.com/s1",
                title="Stub Job",
                description_html="<p>Stub</p>",
                description_text="Stub",
                raw_payload={},
            )
        ]


def test_ingest_requires_token(test_client):
    resp = test_client.post("/api/internal/ingest/run")
    assert resp.status_code == 422  # missing header


def test_ingest_rejects_bad_token(test_client):
    with patch("app.api.deps.get_settings", return_value=_mock_settings()):
        resp = test_client.post(
            "/api/internal/ingest/run",
            headers={"x-internal-token": "wrong"},
        )
    assert resp.status_code == 401


def test_ingest_success(test_client):
    mock_registry = {"stub": _StubAdapter()}

    with (
        patch("app.api.deps.get_settings", return_value=_mock_settings()),
        patch("app.api.routes.internal_ingest.get_settings", return_value=_mock_settings()),
        patch("app.api.routes.internal_ingest.build_registry", return_value=mock_registry),
    ):
        resp = test_client.post(
            "/api/internal/ingest/run",
            headers={"x-internal-token": "test-token-123"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "sources" in data
    assert data["sources"]["stub"]["status"] == "success"
    assert data["sources"]["stub"]["created"] == 1
