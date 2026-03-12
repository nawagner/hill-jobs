import time

import httpx

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
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
