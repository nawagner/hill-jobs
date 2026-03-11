import time

import httpx

USER_AGENT = (
    "LegBranchJobs/1.0 (legislative job aggregator; "
    "https://github.com/hill-jobs)"
)


def fetch_page(client: httpx.Client, url: str, retries: int = 3) -> str:
    for attempt in range(retries):
        resp = client.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
        if resp.status_code == 429 and attempt < retries - 1:
            wait = 2 ** (attempt + 1)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.text
    return ""
