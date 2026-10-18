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


def _job(
    slug: str,
    role_kind: str,
    posted_days_ago: int | None,
    status: str = "open",
    first_seen_days_ago: int | None = None,
) -> Job:
    """A job posted `posted_days_ago` (None: no posting date, like HVAPS and CSOD)
    and first seen by Hill Jobs `first_seen_days_ago`, by default when it was posted."""
    if first_seen_days_ago is None:
        first_seen_days_ago = posted_days_ago
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
        posted_at=NOW - timedelta(days=posted_days_ago) if posted_days_ago is not None else None,
        first_seen_at=NOW - timedelta(days=first_seen_days_ago),
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
    assert "added to Hill Jobs in the past week" in email["html"]
    # The button links to every open match on the site, not just this week's.
    assert 'href="https://hill-jobs.org/?role_kind=communications"' in email["html"]
    assert "See all 2 open jobs matching your filters" in email["html"]
    assert db_session.query(Subscriber).one().last_sent_at is not None


def test_new_means_first_seen_this_week_not_posted_this_week(db_session):
    db_session.add_all([
        # HVAPS and CSOD listings have no posting date.
        _job("undated-new", "communications", None, first_seen_days_ago=2),
        _job("undated-old", "communications", None, first_seen_days_ago=10),
        # Posted weeks ago but only picked up by an ingest this week.
        _job("late-ingest", "communications", 20, first_seen_days_ago=1),
        _job("old", "communications", 20),
        _subscriber("reader@example.com"),
    ])
    db_session.commit()
    outbox = _Outbox()

    _run(db_session, outbox)

    [email] = outbox.sent
    assert email["subject"] == "Hill Jobs Weekly: 2 new positions matching your filters"
    assert "/jobs/undated-new" in email["html"] and "/jobs/late-ingest" in email["html"]
    assert "undated-old" not in email["html"] and "/jobs/old\"" not in email["html"]
    # No filters: the button links to the whole site and doesn't mention filters.
    assert "See all 4 open jobs" in email["html"]
    assert "matching your filters" not in email["html"]
    assert 'href="https://hill-jobs.org"' in email["html"]


def test_reposted_job_counts_as_new(db_session):
    # Ingestion refreshes posted_at when a source reposts a job it listed before.
    db_session.add_all([
        _job("reposted", "communications", 2, first_seen_days_ago=30),
        _subscriber("reader@example.com"),
    ])
    db_session.commit()
    outbox = _Outbox()

    _run(db_session, outbox)

    [email] = outbox.sent
    assert "/jobs/reposted" in email["html"]


def test_100_job_cap_does_not_drop_undated_jobs_first(db_session):
    db_session.add_all([_job(f"dated-{i}", "communications", 2) for i in range(101)])
    db_session.add_all([
        _job("undated", "communications", None, first_seen_days_ago=1),
        _subscriber("reader@example.com"),
    ])
    db_session.commit()
    outbox = _Outbox()

    _run(db_session, outbox)

    [email] = outbox.sent
    assert email["subject"] == "Hill Jobs Weekly: 102 new positions matching your filters"
    assert "/jobs/undated" in email["html"]


def test_date_posted_choice_lists_what_the_site_shows(db_session):
    db_session.add_all([
        _job("this-week", "communications", 2),
        _job("this-month", "communications", 20),
        _job("undated-this-month", "communications", None, first_seen_days_ago=10),
        _job("last-quarter", "communications", 60),
        _subscriber("reader@example.com", {"role_kind": "communications", "freshness": "30"}),
    ])
    db_session.commit()
    outbox = _Outbox()

    _run(db_session, outbox)

    [email] = outbox.sent
    assert email["subject"] == (
        "Hill Jobs Weekly: 3 positions posted in the last 30 days matching your filters"
    )
    assert "Here are the open positions posted in the last 30 days that match your filters." in email["html"]
    for slug in ("this-week", "this-month", "undated-this-month"):
        assert f"/jobs/{slug}" in email["html"]
    assert "last-quarter" not in email["html"]
    assert 'href="https://hill-jobs.org/?role_kind=communications&amp;freshness=30"' in email["html"]
    assert "See all 3 open jobs matching your filters" in email["html"]


def test_last_7_days_choice_gets_the_new_jobs_like_no_choice(db_session):
    db_session.add_all([
        _job("this-week", "communications", 2),
        # Listed under a date before the window, but only ingested this week.
        _job("ingested-late", "communications", 8, first_seen_days_ago=6),
        _job("last-month", "communications", 20),
        _subscriber("reader@example.com", {"role_kind": "communications", "freshness": "7"}),
    ])
    db_session.commit()
    outbox = _Outbox()

    _run(db_session, outbox)

    [email] = outbox.sent
    assert email["subject"] == "Hill Jobs Weekly: 2 new positions matching your filters"
    assert "/jobs/this-week" in email["html"] and "/jobs/ingested-late" in email["html"]
    assert "last-month" not in email["html"]
    assert 'href="https://hill-jobs.org/?role_kind=communications"' in email["html"]
    assert "See all 3 open jobs matching your filters" in email["html"]


def test_older_than_30_days_saved_by_hand_gets_the_new_jobs(db_session):
    # The alert forms don't offer it and the API rejects it; ignore it if present.
    db_session.add_all([
        _job("this-week", "communications", 2),
        _job("last-quarter", "communications", 60),
        _subscriber("reader@example.com", {"freshness": "older_30"}),
    ])
    db_session.commit()
    outbox = _Outbox()

    _run(db_session, outbox)

    [email] = outbox.sent
    assert email["subject"] == "Hill Jobs Weekly: 1 new position matching your filters"
    assert "/jobs/this-week" in email["html"] and "last-quarter" not in email["html"]


def test_site_search_url_matches_the_site_parameters():
    url = send_newsletter._site_search_url

    assert url("https://hill-jobs.org", {}) == "https://hill-jobs.org"
    assert url("https://hill-jobs.org", {"party": "D", "committee": "HSSY"}) == (
        "https://hill-jobs.org/?party=D&committee=HSSY"
    )
    # A saved subcommittee needs its parent committee for the site's menus.
    assert url(
        "https://hill-jobs.org",
        {"organization": "Rep. Sarah McBride", "committee": "HSSY15", "salary_min": "75000", "freshness": "30"},
    ) == (
        "https://hill-jobs.org/?organization=Rep.+Sarah+McBride&committee=HSSY"
        "&subcommittee=HSSY15&freshness=30&salary=75000"
    )
    # "Last 7 days" works like no choice, so the link shows every open match.
    assert url("https://hill-jobs.org", {"party": "D", "freshness": "7"}) == (
        "https://hill-jobs.org/?party=D"
    )


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


def test_test_digest_goes_only_to_the_test_address(db_session):
    db_session.add_all([
        _job("new-comms", "communications", 1),
        _job("new-tech", "technology", 2),
        _job("old-comms", "communications", 10),
        _subscriber("reader@example.com"),
    ])
    db_session.commit()
    outbox = _Outbox()

    total = send_newsletter.send_test_digest(
        db_session, to="tester@example.com", api_key="key",
        site_base_url="https://hill-jobs.org", send=outbox,
    )

    assert total == 2
    [email] = outbox.sent
    assert email["to"] == "tester@example.com"
    assert email["subject"] == "[TEST] Hill Jobs Weekly: 2 new positions"
    assert "/jobs/new-comms" in email["html"] and "/jobs/new-tech" in email["html"]
    assert "See all 3 open jobs" in email["html"]
    assert db_session.query(Subscriber).one().last_sent_at is None
