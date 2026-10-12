import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.models.jobs import Job
from app.models.subscribers import Subscriber

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "send_newsletter.py"
_spec = importlib.util.spec_from_file_location("send_newsletter", _SCRIPT)
send_newsletter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(send_newsletter)

NOW = datetime.now(timezone.utc)


def _job(slug: str, role_kind: str, posted_days_ago: int, status: str = "open") -> Job:
    return Job(
        slug=slug,
        title=f"Job {slug}",
        source_organization="Senate Press",
        source_system="senate-webscribble",
        source_job_id=slug,
        source_url=f"https://example.com/{slug}",
        status=status,
        role_kind=role_kind,
        description_html="<p>x</p>",
        description_text="x",
        search_document=f"Job {slug}",
        posted_at=NOW - timedelta(days=posted_days_ago),
    )


def _subscriber(email: str, filters: dict | None = None, confirmed: bool = True, last_sent_days_ago=None):
    return Subscriber(
        email=email,
        filters=filters or {},
        confirmed=confirmed,
        confirm_token=str(uuid4()),
        unsubscribe_token=str(uuid4()),
        last_sent_at=NOW - timedelta(days=last_sent_days_ago) if last_sent_days_ago is not None else None,
    )


class _Outbox:
    def __init__(self, fail_for: set[str] = frozenset()):
        self.sent: list[dict] = []
        self.fail_for = fail_for

    def __call__(self, *, api_key, to, subject, html):
        if to in self.fail_for:
            raise RuntimeError("resend down")
        self.sent.append({"to": to, "subject": subject, "html": html})


def _run(db_session, outbox, dry_run=False):
    return send_newsletter.send_digests(
        db_session, api_key="key", site_base_url="https://hill-jobs.org",
        now=NOW, send=outbox, dry_run=dry_run,
    )


def test_sends_matching_jobs_from_the_last_week(db_session):
    db_session.add_all([
        _job("new-comms", "communications", 2),
        _job("old-comms", "communications", 10),
        _job("closed-comms", "communications", 1, status="closed"),
        _job("new-tech", "technology", 1),
        _subscriber("comms@example.com", {"role_kind": "communications"}),
    ])
    db_session.commit()
    outbox = _Outbox()

    result = _run(db_session, outbox)

    assert (result.sent, result.skipped, result.errors) == (1, 0, 0)
    [email] = outbox.sent
    assert email["to"] == "comms@example.com"
    assert email["subject"] == "Hill Jobs Weekly: 1 new position matching your filters"
    assert "/jobs/new-comms" in email["html"]
    assert "old-comms" not in email["html"] and "closed-comms" not in email["html"]
    assert db_session.query(Subscriber).one().last_sent_at is not None


def test_skips_unconfirmed_recently_sent_and_no_matches(db_session):
    db_session.add_all([
        _job("new-comms", "communications", 1),
        _subscriber("unconfirmed@example.com", confirmed=False),
        _subscriber("recent@example.com", last_sent_days_ago=3),
        _subscriber("nomatch@example.com", {"role_kind": "legal"}),
        _subscriber("due@example.com", last_sent_days_ago=7),
    ])
    db_session.commit()
    outbox = _Outbox()

    result = _run(db_session, outbox)

    assert [e["to"] for e in outbox.sent] == ["due@example.com"]
    assert (result.sent, result.skipped, result.errors) == (1, 2, 0)


def test_failed_send_is_counted_and_not_marked_sent(db_session):
    db_session.add_all([_job("new-comms", "communications", 1), _subscriber("bounce@example.com")])
    db_session.commit()

    result = _run(db_session, _Outbox(fail_for={"bounce@example.com"}))

    assert result.errors == 1
    assert db_session.query(Subscriber).one().last_sent_at is None


def test_dry_run_sends_nothing_and_records_nothing(db_session):
    db_session.add_all([_job("new-comms", "communications", 1), _subscriber("reader@example.com")])
    db_session.commit()
    outbox = _Outbox()

    result = _run(db_session, outbox, dry_run=True)

    assert result.sent == 1
    assert outbox.sent == []
    assert db_session.query(Subscriber).one().last_sent_at is None


def test_mask_hides_most_of_the_address():
    assert send_newsletter._mask("jane.doe@example.com") == "j***@example.com"
