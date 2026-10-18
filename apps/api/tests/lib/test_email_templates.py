from datetime import datetime, timezone
from types import SimpleNamespace

from app.lib.email_templates import build_digest_html


def test_digest_unsubscribe_link_uses_existing_preferences_route():
    job = SimpleNamespace(
        slug="policy-aide",
        role_kind="policy",
        title="Policy Aide",
        source_organization="Senate Committee on Finance",
        salary_min=None,
        salary_max=None,
        salary_period=None,
        posted_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )

    html = build_digest_html([job], "token-123", "https://hill-jobs.org")

    assert 'href="https://hill-jobs.org/preferences/token-123"' in html
    assert "/unsubscribe/token-123" not in html


def test_digest_escapes_scraped_text():
    job = SimpleNamespace(
        slug="aide",
        role_kind="operations",
        title="Aide <script>alert(1)</script> & Scheduler",
        source_organization="Rep. O'Neil <Office>",
        salary_min=None,
        salary_max=None,
        salary_period=None,
        posted_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )

    html = build_digest_html([job], "token-123", "https://hill-jobs.org")

    assert "<script>" not in html
    assert "Aide &lt;script&gt;alert(1)&lt;/script&gt; &amp; Scheduler" in html
    assert "&lt;Office&gt;" in html


def test_digest_groups_jobs_by_category_then_title():
    def job(slug, role_kind, title, org):
        return SimpleNamespace(
            slug=slug,
            role_kind=role_kind,
            title=title,
            source_organization=org,
            salary_min=None,
            salary_max=None,
            salary_period=None,
            posted_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )

    jobs = [
        job("staff-b", "operations", "Staff Assistant", "Sen. Brown"),
        job("press", "communications", "press secretary", "Rep. Smith"),
        job("counsel", "legal", "Counsel", "Judiciary"),
        job("staff-a", "operations", "Staff Assistant", "Rep. Adams"),
        job("digital", "communications", "Digital Director", "Rep. Jones"),
        job("analyst", "operations", "Budget Analyst", "CBO"),
    ]

    html = build_digest_html(jobs, "token-123", "https://hill-jobs.org")

    expected = [
        "Communications (2)", "/jobs/digital\"", "/jobs/press\"",
        "Legal (1)", "/jobs/counsel\"",
        "Operations (3)", "/jobs/analyst\"", "/jobs/staff-a\"", "/jobs/staff-b\"",
    ]
    positions = [html.index(marker) for marker in expected]
    assert positions == sorted(positions)


def test_digest_links_to_every_open_match_on_the_site():
    job = SimpleNamespace(
        slug="aide",
        role_kind="operations",
        title="Aide",
        source_organization="Rep. Smith",
        salary_min=None,
        salary_max=None,
        salary_period=None,
        posted_at=None,
    )

    html = build_digest_html(
        [job],
        "token-123",
        "https://hill-jobs.org",
        intro="Here are the open positions posted in the last 30 days that match your filters.",
        search_url="https://hill-jobs.org/?party=D&committee=HSSY",
        open_total=8,
        filtered=True,
    )

    assert "posted in the last 30 days that match your filters." in html
    assert 'href="https://hill-jobs.org/?party=D&amp;committee=HSSY"' in html
    assert "See all 8 open jobs matching your filters" in html
    assert "View All Jobs" not in html


def test_digest_see_all_button_singular_and_unfiltered():
    job = SimpleNamespace(
        slug="aide", role_kind="operations", title="Aide", source_organization="Rep. Smith",
        salary_min=None, salary_max=None, salary_period=None, posted_at=None,
    )

    html = build_digest_html([job], "token-123", "https://hill-jobs.org", open_total=1)

    assert "See all 1 open job\n" in html
    assert 'href="https://hill-jobs.org"' in html
