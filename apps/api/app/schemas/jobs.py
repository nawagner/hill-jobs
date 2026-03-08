from datetime import datetime

from pydantic import BaseModel


class JobListItem(BaseModel):
    slug: str
    title: str
    source_system: str
    source_organization: str
    source_url: str
    status: str
    role_kind: str
    location_text: str | None = None
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    salary_period: str | None = None
    posted_at: datetime | None = None
    closing_at: datetime | None = None


class JobDetail(JobListItem):
    source_job_id: str | None = None
    description_html: str
    description_text: str


class OrganizationItem(BaseModel):
    name: str
    source_system: str
    party: str | None = None


class JobSearchResponse(BaseModel):
    items: list[JobListItem]
    total: int
    page: int = 1
    page_size: int = 20
