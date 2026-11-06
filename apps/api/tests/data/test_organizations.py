import pytest

from app.data.organizations import employer_organization, staff_committee

SENATE = "U.S. Senate"
HOUSE = "U.S. House of Representatives"


@pytest.mark.parametrize(
    "source_system, source_organization, organization, committee",
    [
        ("senate-webscribble", "Senator Andy Kim", SENATE, None),
        ("senate-webscribble", "Finance - Democrats", SENATE, "SSFI"),
        ("senate-webscribble", "Banking, Housing, and Urban Affairs - Republicans", SENATE, "SSBK"),
        ("senate-webscribble", "Homeland Security and Governmental Affairs - Democrats", SENATE, "SSGA"),
        ("senate-webscribble", "Senator Richard Blumenthal, Senate Judiciary Committee", SENATE, "SSJU"),
        ("senate-webscribble", "Secretary of the Senate", SENATE, None),
        ("senate-webscribble", "Senate Committees", SENATE, None),
        ("senate-webscribble", "Stars of Valor Fellowships Program", SENATE, None),
        ("senate-webscribble", "Afghanistan War Commission", "Congressional Commissions", None),
        ("senate-webscribble", "U.S.-China Economic and Security Review Commission", "Congressional Commissions", None),
        ("house-dems-resumebank", "House Armed Services Committee", HOUSE, "HSAS"),
        ("house-dems-resumebank", "Judiciary Committee (House)", HOUSE, "HSJU"),
        ("house-dems-resumebank", "House Energy and Commerce Committee", HOUSE, "HSIF"),
        ("house-dems-resumebank", "House Democrats", HOUSE, None),
        ("house-hvaps", "Democratic Staff of the Committee on Rules", HOUSE, "HSRU"),
        ("house-hvaps", "Democratic Staff of the House Committee on Veterans' Affairs", HOUSE, "HSVR"),
        ("csod-house-clerk", "Clerk of the House", HOUSE, None),
        ("csod-house-saa", "Sergeant at Arms", HOUSE, None),
        ("csod-house-green-gold", "Green & Gold Program", HOUSE, None),
        ("aoc-usajobs", "Architect of the Capitol", "Architect of the Capitol", None),
        ("csod-uscp", "U.S. Capitol Police", "U.S. Capitol Police", None),
        ("manual", "Rep. Nathaniel Moran", HOUSE, None),
    ],
)
def test_employer_classification(source_system, source_organization, organization, committee):
    assert employer_organization(source_system, source_organization) == organization
    assert staff_committee(source_system, source_organization) == committee
