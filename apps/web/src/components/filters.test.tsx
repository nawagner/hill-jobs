import { fireEvent, render, screen, within } from "@testing-library/react";
import { Filters } from "./filters";
import type { MemberItem } from "../lib/api";

const members: MemberItem[] = [
  { name: "Senator Andy Kim", chamber: "senate", party: "D", state: "NJ" },
  { name: "Rep. Young Kim", chamber: "house", party: "R", state: "CA" },
];

function renderFilters(overrides: Partial<Parameters<typeof Filters>[0]> = {}) {
  const props = {
    roleKinds: [],
    organizations: [{ name: "U.S. Senate" }, { name: "Library of Congress" }],
    members,
    states: [],
    committees: [],
    selectedRoleKind: "",
    selectedOrganization: "",
    selectedMember: "",
    selectedParty: "",
    selectedState: "",
    selectedCommittee: "",
    selectedSubcommittee: "",
    selectedFreshness: "",
    selectedSalary: "",
    onRoleKindChange: vi.fn(),
    onOrganizationChange: vi.fn(),
    onMemberChange: vi.fn(),
    onPartyChange: vi.fn(),
    onStateChange: vi.fn(),
    onCommitteeChange: vi.fn(),
    onSubcommitteeChange: vi.fn(),
    onFreshnessChange: vi.fn(),
    onSalaryChange: vi.fn(),
    ...overrides,
  };
  render(<Filters {...props} />);
  return props;
}

describe("Filters", () => {
  it("lists only top-level organizations", () => {
    renderFilters();
    const options = within(screen.getByLabelText("Organization")).getAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual([
      "All organizations",
      "U.S. Senate",
      "Library of Congress",
    ]);
  });

  it("groups members by chamber and sets the member filter", () => {
    const props = renderFilters();
    const select = screen.getByLabelText("Member");
    expect(within(select).getByRole("group", { name: "Senators" })).toHaveTextContent("Andy Kim (D-NJ)");
    expect(within(select).getByRole("group", { name: "Representatives" })).toHaveTextContent("Young Kim (R-CA)");
    fireEvent.change(select, { target: { value: "Senator Andy Kim" } });
    expect(props.onMemberChange).toHaveBeenCalledWith("Senator Andy Kim");
    expect(props.onOrganizationChange).not.toHaveBeenCalled();
  });

  it("keeps an old single-office organization visible", () => {
    renderFilters({ selectedOrganization: "Clerk of the House" });
    expect(screen.getByLabelText("Organization")).toHaveValue("Clerk of the House");
  });

  it("keeps a saved member with no open jobs visible", () => {
    renderFilters({ members: [], selectedMember: "Senator Christopher A. Coons" });
    expect(screen.getByLabelText("Member")).toHaveValue("Senator Christopher A. Coons");
  });
});
