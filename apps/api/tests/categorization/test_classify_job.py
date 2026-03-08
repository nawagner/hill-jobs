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


def test_unmatched_defaults_to_operations():
    assert classify_job("Cook", "", "Senate Cafeteria") == "operations"
