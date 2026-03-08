import { formatRoleKind } from "../lib/api";

interface FiltersProps {
  roleKinds: string[];
  organizations: string[];
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
          <option key={org} value={org}>
            {org}
          </option>
        ))}
      </select>

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
