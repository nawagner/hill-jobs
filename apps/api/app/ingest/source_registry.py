from typing import Protocol

import httpx

from app.schemas.ingest import SourceJob


class SourceAdapter(Protocol):
    source_system: str

    def fetch_jobs(self, client: httpx.Client) -> list[SourceJob]: ...
