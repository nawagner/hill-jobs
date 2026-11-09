from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from app.config import Settings
from app.models.subscribers import Subscriber

URL = "/api/internal/subscribers/resend-confirmations"
HEADERS = {"x-internal-token": "test-token-123"}


def _settings(**overrides):
    values = dict(
        database_url="sqlite:///:memory:",
        internal_ingest_token="test-token-123",
        resend_api_key="re_test",
        site_base_url="https://hill-jobs.org",
    )
    values.update(overrides)
    return Settings(**values)


def _add(db_session, email, confirmed, created):
    sub = Subscriber(
        email=email,
        filters={},
        confirmed=confirmed,
        confirm_token=str(uuid4()),
        unsubscribe_token=str(uuid4()),
        created_at=created,
        updated_at=created,
    )
    db_session.add(sub)
    db_session.commit()
    return sub


def _seed(db_session):
    recent = _add(db_session, "new@example.com", False, datetime(2026, 11, 5, tzinfo=timezone.utc))
    _add(db_session, "old@example.com", False, datetime(2026, 10, 1, tzinfo=timezone.utc))
    _add(db_session, "done@example.com", True, datetime(2026, 11, 6, tzinfo=timezone.utc))
    return recent


def _post(test_client, settings, **params):
    with patch("app.api.deps.get_settings", return_value=settings), patch(
        "app.api.routes.internal_subscribers.get_settings", return_value=settings
    ):
        return test_client.post(URL, params=params, headers=HEADERS)


def test_requires_token(test_client):
    assert test_client.post(URL, params={"since": "2026-11-02"}).status_code == 422
    with patch("app.api.deps.get_settings", return_value=_settings()):
        resp = test_client.post(URL, params={"since": "2026-11-02"}, headers={"x-internal-token": "nope"})
    assert resp.status_code == 401


def test_dry_run_lists_recent_unconfirmed_and_sends_nothing(test_client, db_session):
    _seed(db_session)
    with patch("app.api.routes.subscribe.send_email") as send:
        resp = _post(test_client, _settings(), since="2026-11-02", dry_run="true")
    assert resp.status_code == 200
    assert resp.json()["matched"] == ["n***@example.com"]
    assert resp.json()["sent"] == []
    send.assert_not_called()


def test_resends_existing_confirmation_link(test_client, db_session):
    recent = _seed(db_session)
    with patch("app.api.routes.subscribe.send_email") as send:
        resp = _post(test_client, _settings(), since="2026-11-02")
    assert resp.json()["sent"] == ["n***@example.com"]
    send.assert_called_once()
    kwargs = send.call_args.kwargs
    assert kwargs["to"] == "new@example.com"
    assert f"/subscribe/confirm/{recent.confirm_token}" in kwargs["html"]


def test_one_failure_does_not_stop_the_rest(test_client, db_session):
    _seed(db_session)
    _add(db_session, "second@example.com", False, datetime(2026, 11, 7, tzinfo=timezone.utc))
    with patch("app.api.routes.subscribe.send_email", side_effect=[RuntimeError("401"), None]):
        resp = _post(test_client, _settings(), since="2026-11-02")
    body = resp.json()
    assert body["failed"] == ["n***@example.com"]
    assert body["sent"] == ["s***@example.com"]


def test_refuses_to_send_without_resend_key(test_client, db_session):
    _seed(db_session)
    resp = _post(test_client, _settings(resend_api_key=""), since="2026-11-02")
    assert resp.status_code == 500
