import pytest

from app.data.member_committees import COMMITTEES
from app.data.member_data import MEMBERS
from app.data.members import employer_party, find_member


@pytest.mark.parametrize(
    "source_organization, expected",
    [
        # Senators the old table filed under "Rep."
        ("Senator Andy Kim", "Senator Andy Kim"),
        ("Senator Christopher A. Coons", "Senator Christopher A. Coons"),
        ("Senator Chris Coons", "Senator Christopher A. Coons"),
        ("Senator Dick Durbin", "Senator Richard J. Durbin"),
        # Suffixes, middle initials, accents, nicknames
        ("Rep. Emanuel Cleaver, II", "Rep. Emanuel Cleaver"),
        ("Rep. Norma Torres", "Rep. Norma J. Torres"),
        ("Rep. Gilbert R. Cisneros Jr.", "Rep. Gilbert Ray Cisneros"),
        ("Senator Ben Ray Lujan", "Senator Ben Ray Luján"),
        ("Rep. Chuy Garcia", "Rep. Jesús G. García"),
        ("Senator Angus S. King, Jr.", "Senator Angus S. King"),
        # Trailing committee name
        ("Senator Richard Blumenthal, Senate Judiciary Committee", "Senator Richard Blumenthal"),
        # Multi-word last names and other title forms
        ("Senator Catherine Cortez Masto", "Senator Catherine Cortez Masto"),
        ("Rep. Debbie Wasserman Schultz", "Rep. Debbie Wasserman Schultz"),
        ("Office of Congressman Kevin Mullin", "Rep. Kevin Mullin"),
        ("Congresswoman Analilia Mejia", "Rep. Analilia Mejia"),
        # A middle initial that is another member's first initial
        ("Rep. Robert J. Garcia", "Rep. Robert Garcia"),
        ("Rep. Ritchie J. Torres", "Rep. Ritchie Torres"),
        ("Rep. Bennie G. Thompson Jr.", "Rep. Bennie G. Thompson"),
        ("Rep. Ronny L. Jackson", "Rep. Ronny Jackson"),
        # Domewatch's "Cleaver, Emanuel, II - Rep." after _extract_org
        ("Rep. Emanuel, II Cleaver", "Rep. Emanuel Cleaver"),
        ("Rep. Troy A., Sr. Carter", "Rep. Troy A. Carter"),
        # Initials and other title forms
        ("Rep. W. Steube", "Rep. W. Gregory Steube"),
        ("Rep. Greg Steube", "Rep. W. Gregory Steube"),
        ("U.S. Senator Andy Kim", "Senator Andy Kim"),
        ("Rep Jim Clyburn", "Rep. James E. Clyburn"),
    ],
)
def test_find_member_variants(source_organization, expected):
    member = find_member(source_organization)
    assert member is not None
    assert member.name == expected


@pytest.mark.parametrize(
    "source_organization",
    [
        "Rep. Andy Kim",  # Andy Kim is a senator; Young Kim is the House Kim
        "Rep. Nonexistent Person",
        "Rep. Susan M. Collins",  # "M." is not Mike Collins' first name
        "Library of Congress",
        "House Democrats",
        "Senate Employment Office",
        "",
        None,
    ],
)
def test_find_member_misses(source_organization):
    assert find_member(source_organization) is None


def test_senators_and_representatives_match_their_chamber():
    andy_kim = find_member("Senator Andy Kim")
    young_kim = find_member("Rep. Young Kim")
    assert (andy_kim.chamber, andy_kim.party) == ("senate", "D")
    assert (young_kim.chamber, young_kim.party) == ("house", "R")


@pytest.mark.parametrize(
    "source_system, source_organization, expected",
    [
        ("senate-webscribble", "Senator Andy Kim", "D"),
        ("senate-webscribble", "Finance - Democrats", "D"),
        ("senate-webscribble", "Foreign Relations - Republicans", "R"),
        ("house-hvaps", "Democratic Staff of the Committee on Rules", "D"),
        ("house-dems-resumebank", "House Armed Services Committee", "D"),
        ("house-dems-resumebank", "House Democrats", "D"),
        ("senate-webscribble", "Senate Committees", None),
        ("senate-webscribble", "Confidential", None),
        ("aoc-usajobs", "Architect of the Capitol", None),
        ("house-hvaps", "U.S. House of Representatives", None),
    ],
)
def test_employer_party(source_system, source_organization, expected):
    assert employer_party(source_system, source_organization) == expected


def test_every_member_resolves_to_itself():
    """Each canonical name, and each official name, finds its own member."""
    for m in MEMBERS:
        prefix = "Senator " if m["chamber"] == "senate" else "Rep. "
        member = find_member(prefix + m["official_full"])
        assert member is not None and member.id == m["id"], m["official_full"]
        assert find_member(member.name).id == m["id"]


def test_member_committees_exist():
    for m in MEMBERS:
        for code in m["committees"]:
            assert code in COMMITTEES, (m["official_full"], code)
