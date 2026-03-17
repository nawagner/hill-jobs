from datetime import datetime, timezone
from types import SimpleNamespace

from app.lib.email_templates import build_digest_html


def test_digest_unsubscribe_link_uses_existing_preferences_route():
    job = SimpleNamespace(
        slug="policy-aide",
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
