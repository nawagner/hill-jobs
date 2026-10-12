import pytest

from app.categorization.classify_job import classify_job


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Communications Director", "communications"),
        ("Press Secretary", "communications"),
        ("Staff Writer", "communications"),
        ("Legislative Counsel", "legal"),
        ("Staff Attorney", "legal"),
        ("Policy Advisor", "policy"),
        ("Legislative Director", "policy"),
        ("Research Specialist", "policy"),
        ("Software Engineer", "technology"),
        ("Systems Administrator", "technology"),
        ("IT Manager", "technology"),
        ("Cybersecurity Senior Specialist", "security"),
        ("Police Officer", "security"),
        ("Security Manager", "security"),
        ("Protective Services Agent", "security"),
        ("Office Manager", "operations"),
        ("Staff Assistant", "operations"),
        ("Law Clerk", "legal"),
        ("Digital Director", "communications"),
        ("Press Intern", "communications"),
        ("Legislative Intern", "policy"),
        ("Spring 2027 DC Internship", "operations"),
        ("Green & Gold Congressional Aide", "operations"),
        ("Policy Advisor – Banking, Housing, And Consumer Protection", "policy"),
        ("Senior Business Systems Analyst", "technology"),
        ("Law Enforcement Specialist", "security"),
        ("Digital Project Coordinator (GS-13)", "operations"),
        ("Senior Professional Staff Member – Asia", "policy"),
        # A sentence fragment from a bulletin, not "IT".
        ("The office has made it a priority to hire locally", "operations"),
    ],
)
def test_title_classification(title: str, expected: str):
    assert classify_job(title, "", "Some Office") == expected


def test_description_fallback():
    assert (
        classify_job(
            "Senior Advisor",
            "This role focuses on legislative policy development.",
            "Senate",
        )
        == "policy"
    )


def test_org_default_capitol_police():
    assert (
        classify_job(
            "Administrative Specialist",
            "General office duties.",
            "U.S. Capitol Police",
        )
        == "security"
    )


@pytest.mark.parametrize(
    "title,description",
    [
        ("Field Representative", "Requires strong written and oral communication skills."),
        ("Electrician Assistant Supervisor", "Ensures work complies with legal requirements."),
        ("Maintenance Mechanic General Supervisor", "Must be able to obtain a security clearance."),
        ("Scheduler", "Work with press and legislative staff on the Member's schedule."),
    ],
)
def test_skill_and_clearance_mentions_dont_set_category(title: str, description: str):
    assert classify_job(title, description, "Some Office") == "operations"


def test_capitol_police_default_beats_description():
    assert (
        classify_job(
            "Containment and Emergency Response Division (CERD) Sergeant",
            "Coordinates with legal counsel on response plans.",
            "U.S. Capitol Police",
        )
        == "security"
    )


def test_unmatched_defaults_to_operations():
    assert classify_job("Cook", "", "Senate Cafeteria") == "operations"
