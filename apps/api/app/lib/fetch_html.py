import httpx

USER_AGENT = (
    "LegBranchJobs/1.0 (legislative job aggregator; "
    "https://github.com/hill-jobs)"
)


def fetch_page(client: httpx.Client, url: str) -> str:
    resp = client.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    resp.raise_for_status()
    return resp.text
