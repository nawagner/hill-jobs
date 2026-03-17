from __future__ import annotations

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


def build_digest_html(
    jobs: list[Job], unsubscribe_token: str, site_base_url: str
) -> str:
    job_rows = []
    for job in jobs:
        salary = _format_salary(job)
        salary_html = f'<span style="color:#059669;font-size:13px;">{salary}</span><br>' if salary else ""
        posted = ""
        if job.posted_at:
            posted = job.posted_at.strftime("%b %d, %Y")

        job_rows.append(f"""\
    <tr>
      <td style="padding:16px 0;border-bottom:1px solid #e2e8f0;">
        <a href="{site_base_url}/jobs/{job.slug}" style="color:#1e40af;font-weight:600;text-decoration:none;font-size:15px;">
          {job.title}
        </a><br>
        <span style="color:#475569;font-size:13px;">{job.source_organization}</span><br>
        {salary_html}<span style="color:#94a3b8;font-size:12px;">{posted}</span>
      </td>
    </tr>""")

    jobs_html = "\n".join(job_rows)
    preferences_url = f"{site_base_url}/preferences/{unsubscribe_token}"
    unsubscribe_url = f"{site_base_url}/unsubscribe/{unsubscribe_token}"

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
        Here are the latest positions matching your filters from the past week.
      </p>
      <table style="width:100%;border-collapse:collapse;">
{jobs_html}
      </table>
      <div style="margin-top:24px;text-align:center;">
        <a href="{site_base_url}"
           style="display:inline-block;background:#fbbf24;color:#0f172a;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">
          View All Jobs
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
