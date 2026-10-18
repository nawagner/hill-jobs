from datetime import datetime, timedelta, timezone

from app.models.jobs import Job


def _seed_jobs(db_session):
    now = datetime.now(timezone.utc)
    jobs = [
        Job(
            slug="senate-101",
            title="Software Engineer",
            source_organization="Senate IT",
            source_system="senate-webscribble",
            source_job_id="101",
            source_url="https://example.com/101",
            status="open",
            role_kind="technology",
            description_html="<p>Build systems</p>",
            description_text="Build systems",
            search_document="Software Engineer Build systems",
            posted_at=now,
        ),
        Job(
            slug="senate-102",
            title="Communications Director",
            source_organization="Senate Press",
            source_system="senate-webscribble",
            source_job_id="102",
            source_url="https://example.com/102",
            status="open",
            role_kind="communications",
            description_html="<p>Manage press</p>",
            description_text="Manage press",
            search_document="Communications Director Manage press",
            posted_at=now,
        ),
        Job(
            slug="loc-201",
            title="Librarian",
            source_organization="Library of Congress",
            source_system="loc-careers",
            source_job_id="201",
            source_url="https://example.com/201",
            status="open",
            role_kind="operations",
            description_html="<p>Catalog books</p>",
            description_text="Catalog books",
            search_document="Librarian Catalog books",
            posted_at=now,
        ),
        Job(
            slug="senate-closed",
            title="Policy Analyst",
            source_organization="Senate IT",
            source_system="senate-webscribble",
            source_job_id="999",
            source_url="https://example.com/999",
            status="closed",
            role_kind="policy",
            description_html="<p>Closed role</p>",
            description_text="Closed role",
            search_document="Policy Analyst Closed role",
            posted_at=now,
        ),
    ]
    for j in jobs:
        db_session.add(j)
    db_session.commit()


def test_list_jobs_excludes_closed(test_client, db_session):
    _seed_jobs(db_session)
    resp = test_client.get("/api/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    slugs = [item["slug"] for item in data["items"]]
    assert "senate-closed" not in slugs


def test_list_jobs_filter_by_role_kind(test_client, db_session):
    _seed_jobs(db_session)
    resp = test_client.get("/api/jobs", params={"role_kind": "technology"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["slug"] == "senate-101"


def test_list_jobs_filter_by_organization(test_client, db_session):
    _seed_jobs(db_session)
    resp = test_client.get("/api/jobs", params={"organization": "Library of Congress"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["slug"] == "loc-201"


def test_list_jobs_keyword_search(test_client, db_session):
    _seed_jobs(db_session)
    resp = test_client.get("/api/jobs", params={"q": "Engineer"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["slug"] == "senate-101"


def test_list_jobs_keyword_search_by_organization(test_client, db_session):
    _seed_jobs(db_session)
    resp = test_client.get("/api/jobs", params={"q": "Library of Congress"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["slug"] == "loc-201"


def test_get_job_detail(test_client, db_session):
    _seed_jobs(db_session)
    resp = test_client.get("/api/jobs/senate-101")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Software Engineer"
    assert data["source_system"] == "senate-webscribble"
    assert data["description_html"] == "<p>Build systems</p>"


def test_get_job_not_found(test_client, db_session):
    resp = test_client.get("/api/jobs/nonexistent")
    assert resp.status_code == 404


def test_list_organizations(test_client, db_session):
    _seed_jobs(db_session)
    resp = test_client.get("/api/organizations")
    assert resp.status_code == 200
    orgs = resp.json()
    org_names = [o["name"] for o in orgs]
    assert "Library of Congress" in org_names
    assert "Senate IT" in org_names
    # Closed job org should still appear if other open jobs share it
    assert len(orgs) == 3
    # Each org includes source_system and party
    for o in orgs:
        assert "source_system" in o
        assert "party" in o


def _seed_jobs_with_salaries(db_session):
    now = datetime.now(timezone.utc)
    jobs = [
        Job(
            slug="high-salary",
            title="Senior Advisor",
            source_organization="Senate IT",
            source_system="senate-webscribble",
            source_job_id="301",
            source_url="https://example.com/301",
            status="open",
            role_kind="policy",
            description_html="<p>Advise</p>",
            description_text="Advise",
            posted_at=now,
            salary_min=120000,
            salary_max=150000,
            salary_period="annual",
        ),
        Job(
            slug="mid-salary",
            title="Analyst",
            source_organization="Senate IT",
            source_system="senate-webscribble",
            source_job_id="302",
            source_url="https://example.com/302",
            status="open",
            role_kind="policy",
            description_html="<p>Analyze</p>",
            description_text="Analyze",
            posted_at=now,
            salary_min=60000,
            salary_max=80000,
            salary_period="annual",
        ),
        Job(
            slug="no-salary",
            title="Intern",
            source_organization="Senate IT",
            source_system="senate-webscribble",
            source_job_id="303",
            source_url="https://example.com/303",
            status="open",
            role_kind="operations",
            description_html="<p>Intern</p>",
            description_text="Intern",
            posted_at=now,
        ),
    ]
    for j in jobs:
        db_session.add(j)
    db_session.commit()


def test_salary_filter_has_salary(test_client, db_session):
    _seed_jobs_with_salaries(db_session)
    resp = test_client.get("/api/jobs", params={"salary_min": 0})
    data = resp.json()
    assert data["total"] == 2
    slugs = {item["slug"] for item in data["items"]}
    assert slugs == {"high-salary", "mid-salary"}


def test_salary_filter_minimum_threshold(test_client, db_session):
    _seed_jobs_with_salaries(db_session)
    resp = test_client.get("/api/jobs", params={"salary_min": 100000})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["slug"] == "high-salary"


def test_list_role_kinds(test_client):
    resp = test_client.get("/api/role-kinds")
    assert resp.status_code == 200
    data = resp.json()
    assert data == ["policy", "communications", "legal", "operations", "technology", "security"]


# --- Party / State / Committee filter tests ---


def _seed_member_jobs(db_session):
    """Seed jobs from actual member names that exist in lookup dicts."""
    now = datetime.now(timezone.utc)
    jobs = [
        Job(
            slug="schiff-la",
            title="Legislative Assistant",
            source_organization="Senator Adam B. Schiff",
            source_system="senate-webscribble",
            source_job_id="401",
            source_url="https://example.com/401",
            status="open",
            role_kind="policy",
            description_html="<p>LA role</p>",
            description_text="LA role",
            posted_at=now,
        ),
        Job(
            slug="collins-la",
            title="Staff Assistant",
            source_organization="Senator Susan M. Collins",
            source_system="senate-webscribble",
            source_job_id="402",
            source_url="https://example.com/402",
            status="open",
            role_kind="operations",
            description_html="<p>SA role</p>",
            description_text="SA role",
            posted_at=now,
        ),
        Job(
            slug="aoc-comms",
            title="Communications Director",
            source_organization="Rep. Alexandria Ocasio-Cortez",
            source_system="house-dems-resumebank",
            source_job_id="403",
            source_url="https://example.com/403",
            status="open",
            role_kind="communications",
            description_html="<p>Comms role</p>",
            description_text="Comms role",
            posted_at=now,
        ),
        Job(
            slug="loc-job",
            title="Archivist",
            source_organization="Library of Congress",
            source_system="loc-careers",
            source_job_id="404",
            source_url="https://example.com/404",
            status="open",
            role_kind="operations",
            description_html="<p>Archive</p>",
            description_text="Archive",
            posted_at=now,
        ),
    ]
    for j in jobs:
        db_session.add(j)
    db_session.commit()


def test_filter_by_party_democrat(test_client, db_session):
    _seed_member_jobs(db_session)
    resp = test_client.get("/api/jobs", params={"party": "D"})
    data = resp.json()
    slugs = {item["slug"] for item in data["items"]}
    assert "schiff-la" in slugs
    assert "aoc-comms" in slugs
    assert "collins-la" not in slugs  # Republican
    assert "loc-job" not in slugs  # Not a member


def test_filter_by_party_republican(test_client, db_session):
    _seed_member_jobs(db_session)
    resp = test_client.get("/api/jobs", params={"party": "R"})
    data = resp.json()
    slugs = {item["slug"] for item in data["items"]}
    assert "collins-la" in slugs
    assert "schiff-la" not in slugs
    assert "aoc-comms" not in slugs


def test_filter_by_state(test_client, db_session):
    _seed_member_jobs(db_session)
    # Schiff and AOC are CA and NY respectively
    resp = test_client.get("/api/jobs", params={"state": "CA"})
    data = resp.json()
    slugs = {item["slug"] for item in data["items"]}
    assert "schiff-la" in slugs
    assert "collins-la" not in slugs  # ME
    assert "aoc-comms" not in slugs  # NY


def test_filter_by_state_excludes_institutional(test_client, db_session):
    _seed_member_jobs(db_session)
    resp = test_client.get("/api/jobs", params={"state": "DC"})
    data = resp.json()
    # No members represent DC in our test data
    assert data["total"] == 0


def test_combined_party_and_state(test_client, db_session):
    _seed_member_jobs(db_session)
    # Democrat + California = only Schiff
    resp = test_client.get("/api/jobs", params={"party": "D", "state": "CA"})
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["slug"] == "schiff-la"


def test_list_states_endpoint(test_client):
    resp = test_client.get("/api/states")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    # Each item has code and name
    assert all("code" in s and "name" in s for s in data)
    # California should be in there
    codes = [s["code"] for s in data]
    assert "CA" in codes


def test_list_committees_endpoint(test_client):
    resp = test_client.get("/api/committees")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    # Each item has id, name, chamber, subcommittees
    for c in data:
        assert "id" in c
        assert "name" in c
        assert "chamber" in c
        assert "subcommittees" in c


def _dated_job(slug: str, posted_days_ago: int | None, first_seen_days_ago: int) -> Job:
    now = datetime.now(timezone.utc)
    return Job(
        slug=slug,
        title=f"Job {slug}",
        source_organization="Senate Press",
        source_system="house-hvaps" if posted_days_ago is None else "senate-webscribble",
        source_job_id=slug,
        source_url=f"https://example.com/{slug}",
        status="open",
        role_kind="operations",
        description_html="<p>x</p>",
        description_text="x",
        search_document=f"Job {slug}",
        posted_at=now - timedelta(days=posted_days_ago) if posted_days_ago is not None else None,
        first_seen_at=now - timedelta(days=first_seen_days_ago),
    )


def test_date_filters_date_undated_jobs_by_when_first_seen(test_client, db_session):
    db_session.add_all([
        _dated_job("posted-recently", 2, 2),
        _dated_job("posted-long-ago", 60, 60),
        _dated_job("undated-recent", None, 3),
        _dated_job("undated-old", None, 45),
    ])
    db_session.commit()

    recent = test_client.get("/api/jobs?posted_since_days=7").json()
    older = test_client.get("/api/jobs?posted_before_days=30").json()

    assert sorted(j["slug"] for j in recent["items"]) == ["posted-recently", "undated-recent"]
    assert sorted(j["slug"] for j in older["items"]) == ["posted-long-ago", "undated-old"]
