import { useMemo } from "react";
import { formatRoleKind } from "../lib/api";
import type { MemberItem, OrganizationItem, StateItem, CommitteeItem } from "../lib/api";

interface FiltersProps {
  roleKinds: string[];
  /** Top-level organizations ("U.S. Senate", "Library of Congress"). */
  organizations: OrganizationItem[];
  members: MemberItem[];
  states: StateItem[];
  committees: CommitteeItem[];
  selectedRoleKind: string;
  selectedOrganization: string;
  selectedMember: string;
  selectedParty: string;
  selectedState: string;
  selectedCommittee: string;
  selectedSubcommittee: string;
  selectedFreshness: string;
  selectedSalary: string;
  onRoleKindChange: (value: string) => void;
  onOrganizationChange: (value: string) => void;
  onMemberChange: (value: string) => void;
  onPartyChange: (value: string) => void;
  onStateChange: (value: string) => void;
  onCommitteeChange: (value: string) => void;
  onSubcommitteeChange: (value: string) => void;
  onFreshnessChange: (value: string) => void;
  onSalaryChange: (value: string) => void;
  /** Weekly alerts are about recent jobs, so their forms leave out "Older than 30 days". */
  showOlderThan30?: boolean;
}

const salaryOptions = [
  { label: "Salary", value: "" },
  { label: "Has salary listed", value: "0" },
  { label: "$50,000+", value: "50000" },
  { label: "$75,000+", value: "75000" },
  { label: "$100,000+", value: "100000" },
  { label: "$150,000+", value: "150000" },
];

const freshnessOptions = [
  { label: "Date posted", value: "" },
  { label: "Last 7 days", value: "7" },
  { label: "Last 30 days", value: "30" },
  { label: "Older than 30 days", value: "older_30" },
];

export function Filters({
  roleKinds,
  organizations,
  members,
  states,
  committees,
  selectedRoleKind,
  selectedOrganization,
  selectedMember,
  selectedParty,
  selectedState,
  selectedCommittee,
  selectedSubcommittee,
  selectedFreshness,
  selectedSalary,
  onRoleKindChange,
  onOrganizationChange,
  onMemberChange,
  onPartyChange,
  onStateChange,
  onCommitteeChange,
  onSubcommitteeChange,
  onFreshnessChange,
  onSalaryChange,
  showOlderThan30 = true,
}: FiltersProps) {
  // A saved alert or link can name a member with no open jobs right now, who
  // isn't in the list; keep the choice visible so it can be seen and cleared.
  const unlistedMember =
    selectedMember && !members.some((m) => m.name === selectedMember) ? selectedMember : "";

  const { senators, representatives } = useMemo(
    () => ({
      senators: members.filter((m) => m.chamber === "senate"),
      representatives: members.filter((m) => m.chamber === "house"),
    }),
    [members],
  );

  // A saved alert or old link can name a single office ("Clerk of the House")
  // from before organizations were grouped; keep it visible so it can be cleared.
  const legacyOrganization =
    selectedOrganization && !organizations.some((o) => o.name === selectedOrganization)
      ? selectedOrganization
      : "";

  const { senateCommittees, houseCommittees, jointCommittees } = useMemo(() => {
    const senate: CommitteeItem[] = [];
    const house: CommitteeItem[] = [];
    const joint: CommitteeItem[] = [];
    for (const c of committees) {
      if (c.chamber === "senate") senate.push(c);
      else if (c.chamber === "house") house.push(c);
      else if (c.chamber === "joint") joint.push(c);
    }
    return { senateCommittees: senate, houseCommittees: house, jointCommittees: joint };
  }, [committees]);

  const selectedCommitteeItem = useMemo(() => {
    if (!selectedCommittee) return null;
    return committees.find((c) => c.id === selectedCommittee) ?? null;
  }, [committees, selectedCommittee]);

  const selectClasses =
    "rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-body text-slate-700 focus:border-gold-400 focus:outline-none focus:ring-2 focus:ring-gold-400/30";

  return (
    <div className="flex flex-wrap gap-3" role="group" aria-label="Filters">
      <select
        aria-label="Role category"
        value={selectedRoleKind}
        onChange={(e) => onRoleKindChange(e.target.value)}
        className={selectClasses}
      >
        <option value="">All categories</option>
        {roleKinds.map((kind) => (
          <option key={kind} value={kind}>
            {formatRoleKind(kind)}
          </option>
        ))}
      </select>

      <select
        aria-label="Organization"
        value={selectedOrganization}
        onChange={(e) => onOrganizationChange(e.target.value)}
        className={selectClasses}
      >
        <option value="">All organizations</option>
        {organizations.map((org) => (
          <option key={org.name} value={org.name}>
            {org.name}
          </option>
        ))}
        {legacyOrganization && <option value={legacyOrganization}>{legacyOrganization}</option>}
      </select>

      {(members.length > 0 || unlistedMember) && (
        <select
          aria-label="Member"
          value={selectedMember}
          onChange={(e) => onMemberChange(e.target.value)}
          className={selectClasses}
        >
          <option value="">All members</option>
          {[
            { label: "Senators", items: senators },
            { label: "Representatives", items: representatives },
          ].map(
            (group) =>
              group.items.length > 0 && (
                <optgroup key={group.label} label={group.label}>
                  {group.items.map((mem) => (
                    <option key={mem.name} value={mem.name}>
                      {mem.name.replace(/^(Senator |Rep\. )/, "")} ({mem.party}-{mem.state})
                    </option>
                  ))}
                </optgroup>
              ),
          )}
          {unlistedMember && (
            <option value={unlistedMember}>{unlistedMember.replace(/^(Senator |Rep\. )/, "")}</option>
          )}
        </select>
      )}

      <select
        aria-label="Party"
        value={selectedParty}
        onChange={(e) => onPartyChange(e.target.value)}
        className={selectClasses}
      >
        <option value="">All parties</option>
        <option value="D">Democrat</option>
        <option value="R">Republican</option>
        <option value="I">Independent</option>
      </select>

      <select
        aria-label="State"
        value={selectedState}
        onChange={(e) => onStateChange(e.target.value)}
        className={selectClasses}
      >
        <option value="">All states</option>
        {states.map((s) => (
          <option key={s.code} value={s.code}>
            {s.name}
          </option>
        ))}
      </select>

      <select
        aria-label="Committee"
        value={selectedCommittee}
        onChange={(e) => onCommitteeChange(e.target.value)}
        className={selectClasses}
      >
        <option value="">All committees</option>
        {senateCommittees.length > 0 && (
          <optgroup label="Senate">
            {senateCommittees.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </optgroup>
        )}
        {houseCommittees.length > 0 && (
          <optgroup label="House">
            {houseCommittees.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </optgroup>
        )}
        {jointCommittees.length > 0 && (
          <optgroup label="Joint">
            {jointCommittees.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </optgroup>
        )}
      </select>

      <select
        aria-label="Subcommittee"
        value={selectedSubcommittee}
        onChange={(e) => onSubcommitteeChange(e.target.value)}
        disabled={!selectedCommitteeItem || selectedCommitteeItem.subcommittees.length === 0}
        className={selectClasses + (!selectedCommitteeItem || selectedCommitteeItem.subcommittees.length === 0 ? " opacity-50 cursor-not-allowed" : "")}
      >
        <option value="">
          {selectedCommitteeItem && selectedCommitteeItem.subcommittees.length > 0
            ? "All subcommittees"
            : "Subcommittee"}
        </option>
        {selectedCommitteeItem?.subcommittees.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>

      <select
        aria-label="Posted within"
        value={selectedFreshness}
        onChange={(e) => onFreshnessChange(e.target.value)}
        className={selectClasses}
      >
        {freshnessOptions
          .filter((opt) => showOlderThan30 || opt.value !== "older_30")
          .map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
      </select>

      <select
        aria-label="Salary"
        value={selectedSalary}
        onChange={(e) => onSalaryChange(e.target.value)}
        className={selectClasses}
      >
        {salaryOptions.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
