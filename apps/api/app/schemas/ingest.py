from datetime import datetime

from pydantic import BaseModel


class SourceJob(BaseModel):
    source_system: str
    source_organization: str
    source_job_id: str | None = None
    source_url: str
    title: str
    description_html: str
    description_text: str
    location_text: str | None = None
    employment_type: str | None = None
    posted_at: datetime | None = None
    closing_at: datetime | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_period: str | None = None
    raw_payload: dict = {}
