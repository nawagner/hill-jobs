import { useMemo } from "react";
import { formatRoleKind } from "../lib/api";
import type { OrganizationItem } from "../lib/api";

interface FiltersProps {
  roleKinds: string[];
  organizations: OrganizationItem[];
  selectedRoleKind: string;
  selectedOrganization: string;
  selectedFreshness: string;
  onRoleKindChange: (value: string) => void;
  onOrganizationChange: (value: string) => void;
  onFreshnessChange: (value: string) => void;
}

const freshnessOptions = [
  { label: "Any time", value: "" },
  { label: "Last 7 days", value: "7" },
  { label: "Last 30 days", value: "30" },
  { label: "Last 90 days", value: "90" },
];

const CHAMBER_LABELS: Record<string, string> = {
  senate: "Senate",
  house: "House",
  legislative: "Legislative Branch",
};

const SOURCE_TO_CHAMBER: Record<string, string> = {
  "senate-webscribble": "senate",
  "csod-house-cao": "house",
  "house-bulletin": "house",
  "house-dems-resumebank": "house",
  "csod-uscp": "legislative",
  "loc-careers": "legislative",
  "aoc-usajobs": "legislative",
};

function stripPartySuffix(name: string): string {
  return name.replace(/ - (Democrats|Republicans|Non-designated)$/, "");
}

export function Filters({
  roleKinds,
  organizations,
  selectedRoleKind,
  selectedOrganization,
  selectedFreshness,
  onRoleKindChange,
  onOrganizationChange,
  onFreshnessChange,
}: FiltersProps) {
  const { officeGroups, members } = useMemo(() => {
    const mems: OrganizationItem[] = [];
    const grouped: Record<string, OrganizationItem[]> = {
      senate: [],
      house: [],
      legislative: [],
    };

    for (const org of organizations) {
      if (org.name.startsWith("Senator ") || org.name === "Confidential") {
        mems.push(org);
      } else {
        const chamber = SOURCE_TO_CHAMBER[org.source_system] || "legislative";
        grouped[chamber].push(org);
      }
    }

    return { officeGroups: grouped, members: mems };
  }, [organizations]);

  const isMemberSelected =
    selectedOrganization.startsWith("Senator ") ||
    selectedOrganization === "Confidential";

  const selectClasses =
    "rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-body text-slate-700 focus:border-gold-400 focus:outline-none focus:ring-2 focus:ring-gold-400/30";

  const chamberOrder = ["senate", "house", "legislative"] as const;

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
        value={isMemberSelected ? "" : selectedOrganization}
        onChange={(e) => onOrganizationChange(e.target.value)}
        className={selectClasses}
      >
        <option value="">All organizations</option>
        {chamberOrder.map((chamber) => {
          const orgs = officeGroups[chamber];
          if (orgs.length === 0) return null;
          return (
            <optgroup key={chamber} label={CHAMBER_LABELS[chamber]}>
              {orgs.map((org) => (
                <option key={org.name} value={org.name}>
                  {stripPartySuffix(org.name)}
                </option>
              ))}
            </optgroup>
          );
        })}
      </select>

      {members.length > 0 && (
        <select
          aria-label="Member"
          value={isMemberSelected ? selectedOrganization : ""}
          onChange={(e) => onOrganizationChange(e.target.value)}
          className={selectClasses}
        >
          <option value="">All members</option>
          {members.map((mem) => {
            const displayName = mem.name.replace(/^Senator /, "");
            const partyLabel = mem.party ? ` (${mem.party})` : "";
            return (
              <option key={mem.name} value={mem.name}>
                {displayName}{partyLabel}
              </option>
            );
          })}
        </select>
      )}

      <select
        aria-label="Posted within"
        value={selectedFreshness}
        onChange={(e) => onFreshnessChange(e.target.value)}
        className={selectClasses}
      >
        {freshnessOptions.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}
