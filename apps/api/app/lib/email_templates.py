from __future__ import annotations

from html import escape
from itertools import groupby
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.jobs import Job


def _format_salary(job: Job) -> str:
    if job.salary_min is None and job.salary_max is None:
        return ""
    parts = []
    if job.salary_min is not None:
        parts.append(f"${int(job.salary_min):,}")
    if job.salary_max is not None:
        parts.append(f"${int(job.salary_max):,}")
    salary = " - ".join(parts)
    if job.salary_period:
        salary += f" ({job.salary_period})"
    return salary


def build_confirmation_html(confirm_url: str) -> str:
    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:system-ui,-apple-system,sans-serif;">
  <div style="max-width:480px;margin:40px auto;background:#fff;border-radius:8px;overflow:hidden;border:1px solid #e2e8f0;">
    <div style="background:#0f172a;padding:24px 32px;">
      <h1 style="margin:0;color:#fbbf24;font-size:20px;">Hill Jobs</h1>
    </div>
    <div style="padding:32px;">
      <h2 style="margin:0 0 16px;color:#1e293b;font-size:18px;">Confirm your subscription</h2>
      <p style="color:#475569;line-height:1.6;margin:0 0 24px;">
        Click the button below to start receiving weekly job alerts matching your filter preferences.
      </p>
      <a href="{confirm_url}"
         style="display:inline-block;background:#fbbf24;color:#0f172a;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">
        Confirm Subscription
      </a>
      <p style="color:#94a3b8;font-size:12px;margin:24px 0 0;">
        If you didn't sign up for Hill Jobs alerts, you can ignore this email.
      </p>
    </div>
  </div>
</body>
</html>"""


NEW_JOBS_INTRO = "Here are the positions added to Hill Jobs in the past week that match your filters."


def build_digest_html(
    jobs: list[Job],
    unsubscribe_token: str,
    site_base_url: str,
    *,
    intro: str = NEW_JOBS_INTRO,
    search_url: str | None = None,
    open_total: int | None = None,
    filtered: bool = False,
) -> str:
    """Render the weekly digest.

    `search_url` and `open_total` power the button under the list, which links
    to the site's search showing every open job that matches the subscriber's
    filters.
    """
    job_rows = []
    # Grouped by category, then alphabetical by title: the jobs were posted within
    # days of each other, so posting order just looks random.
    for role_kind, group in groupby(sorted(jobs, key=_digest_sort_key), key=lambda j: _digest_sort_key(j)[0]):
        group = list(group)
        padding_top = 8 if not job_rows else 28
        job_rows.append(f"""\
    <tr>
      <td style="padding:{padding_top}px 0 6px;border-bottom:2px solid #0f172a;color:#0f172a;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;">
        {escape(role_kind.capitalize())} ({len(group)})
      </td>
    </tr>""")
        job_rows.extend(_digest_job_row(job, site_base_url) for job in group)

    jobs_html = "\n".join(job_rows)
    preferences_url = f"{site_base_url}/preferences/{unsubscribe_token}"
    unsubscribe_url = preferences_url
    if open_total is None:
        see_all_label = "View All Jobs"
    else:
        see_all_label = f"See all {open_total} open job{'' if open_total == 1 else 's'}"
        if filtered:
            see_all_label += " matching your filters"
    see_all_url = search_url or site_base_url

    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f8fafc;font-family:system-ui,-apple-system,sans-serif;">
  <div style="max-width:560px;margin:40px auto;background:#fff;border-radius:8px;overflow:hidden;border:1px solid #e2e8f0;">
    <div style="background:#0f172a;padding:24px 32px;">
      <h1 style="margin:0;color:#fbbf24;font-size:20px;">Hill Jobs Weekly</h1>
    </div>
    <div style="padding:32px;">
      <p style="color:#475569;line-height:1.6;margin:0 0 24px;">
        {escape(intro)}
      </p>
      <table style="width:100%;border-collapse:collapse;">
{jobs_html}
      </table>
      <div style="margin-top:24px;text-align:center;">
        <a href="{escape(see_all_url)}"
           style="display:inline-block;background:#fbbf24;color:#0f172a;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">
          {escape(see_all_label)}
        </a>
      </div>
    </div>
    <div style="background:#f8fafc;padding:20px 32px;text-align:center;border-top:1px solid #e2e8f0;">
      <p style="color:#94a3b8;font-size:12px;margin:0;">
        <a href="{preferences_url}" style="color:#64748b;text-decoration:underline;">Update preferences</a>
        &nbsp;&middot;&nbsp;
        <a href="{unsubscribe_url}" style="color:#64748b;text-decoration:underline;">Unsubscribe</a>
      </p>
    </div>
  </div>
</body>
</html>"""


def _digest_sort_key(job: Job) -> tuple[str, str, str]:
    return (
        (job.role_kind or "other").casefold(),
        job.title.strip().casefold(),
        (job.source_organization or "").casefold(),
    )


def _digest_job_row(job: Job, site_base_url: str) -> str:
    salary = _format_salary(job)
    salary_html = f'<span style="color:#059669;font-size:13px;">{salary}</span><br>' if salary else ""
    posted = ""
    if job.posted_at:
        posted = job.posted_at.strftime("%b %d, %Y")

    return f"""\
    <tr>
      <td style="padding:16px 0;border-bottom:1px solid #e2e8f0;">
        <a href="{site_base_url}/jobs/{job.slug}" style="color:#1e40af;font-weight:600;text-decoration:none;font-size:15px;">
          {escape(job.title)}
        </a><br>
        <span style="color:#475569;font-size:13px;">{escape(job.source_organization or "")}</span><br>
        {salary_html}<span style="color:#94a3b8;font-size:12px;">{posted}</span>
      </td>
    </tr>"""
