import httpx


def send_email(
    api_key: str,
    to: str,
    subject: str,
    html: str,
    from_addr: str = "Hill Jobs <alerts@newsletters.hill-jobs.org>",
) -> None:
    resp = httpx.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": from_addr,
            "to": [to],
            "subject": subject,
            "html": html,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
