import { useEffect, useState, useCallback } from "react";
import { useParams } from "react-router";
import type { OrganizationItem, StateItem, CommitteeItem } from "../lib/api";
import {
  getOrganizations,
  getRoleKinds,
  getStates,
  getCommittees,
  getPreferences,
  updatePreferences,
  unsubscribe,
} from "../lib/api";
import { Filters } from "../components/filters";

export function Preferences() {
  const { token } = useParams<{ token: string }>();

  const [email, setEmail] = useState("");
  const [roleKind, setRoleKind] = useState("");
  const [organization, setOrganization] = useState("");
  const [party, setParty] = useState("");
  const [state, setState] = useState("");
  const [committee, setCommittee] = useState("");
  const [subcommittee, setSubcommittee] = useState("");
  const [freshness, setFreshness] = useState("");
  const [salary, setSalary] = useState("");

  const [organizations, setOrganizations] = useState<OrganizationItem[]>([]);
  const [roleKinds, setRoleKinds] = useState<string[]>([]);
  const [states, setStates] = useState<StateItem[]>([]);
  const [committees, setCommittees] = useState<CommitteeItem[]>([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [unsubscribed, setUnsubscribed] = useState(false);

  useEffect(() => {
    if (!token) return;
    Promise.all([
      getPreferences(token),
      getOrganizations(),
      getRoleKinds(),
      getStates(),
      getCommittees(),
    ])
      .then(([prefs, orgs, kinds, sts, cmts]) => {
        setEmail(prefs.email);
        const f = prefs.filters || {};
        setRoleKind(f.role_kind || "");
        setOrganization(f.organization || "");
        setParty(f.party || "");
        setState(f.state || "");
        setCommittee(f.committee || "");
        setSalary(f.salary_min || "");
        setOrganizations(orgs);
        setRoleKinds(kinds);
        setStates(sts);
        setCommittees(cmts);
      })
      .catch(() => setMessage({ type: "error", text: "Failed to load preferences." }))
      .finally(() => setLoading(false));
  }, [token]);

  const handleCommitteeChange = useCallback((value: string) => {
    setCommittee(value);
    setSubcommittee("");
  }, []);

  const handleSave = async () => {
    if (!token) return;
    setSaving(true);
    setMessage(null);

    const filters: Record<string, string> = {};
    if (roleKind) filters.role_kind = roleKind;
    if (organization) filters.organization = organization;
    if (party) filters.party = party;
    if (state) filters.state = state;
    const effectiveCommittee = subcommittee || committee;
    if (effectiveCommittee) filters.committee = effectiveCommittee;
    if (salary) filters.salary_min = salary;

    try {
      const res = await updatePreferences(token, filters);
      setMessage({ type: "success", text: res.message });
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "Update failed." });
    } finally {
      setSaving(false);
    }
  };

  const handleUnsubscribe = async () => {
    if (!token || !confirm("Are you sure you want to unsubscribe?")) return;
    try {
      await unsubscribe(token);
      setUnsubscribed(true);
    } catch (err) {
      setMessage({ type: "error", text: err instanceof Error ? err.message : "Unsubscribe failed." });
    }
  };

  if (unsubscribed) {
    return (
      <main className="mx-auto max-w-md px-6 py-20 text-center">
        <div className="rounded-lg border border-slate-200 bg-white p-8">
          <h1 className="font-display text-xl font-bold text-slate-800">Unsubscribed</h1>
          <p className="mt-2 font-body text-sm text-slate-500">
            You won't receive any more emails from Hill Jobs.
          </p>
        </div>
      </main>
    );
  }

  if (loading) {
    return (
      <main className="mx-auto max-w-md px-6 py-20">
        <div className="flex justify-center py-8" role="status">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-navy-200 border-t-navy-600" />
          <span className="sr-only">Loading preferences...</span>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <div className="text-center mb-8">
        <h1 className="font-display text-3xl font-bold text-navy-900">Subscription Preferences</h1>
        <p className="mt-2 font-body text-sm text-slate-500">
          Manage your weekly digest filters for <strong>{email}</strong>.
        </p>
      </div>

      <div className="space-y-6">
        <div>
          <p className="block text-sm font-body font-medium text-slate-700 mb-2">
            Filter preferences
          </p>
          <Filters
            roleKinds={roleKinds}
            organizations={organizations}
            states={states}
            committees={committees}
            selectedRoleKind={roleKind}
            selectedOrganization={organization}
            selectedParty={party}
            selectedState={state}
            selectedCommittee={committee}
            selectedSubcommittee={subcommittee}
            selectedFreshness={freshness}
            selectedSalary={salary}
            onRoleKindChange={setRoleKind}
            onOrganizationChange={setOrganization}
            onPartyChange={setParty}
            onStateChange={setState}
            onCommitteeChange={handleCommitteeChange}
            onSubcommitteeChange={setSubcommittee}
            onFreshnessChange={setFreshness}
            onSalaryChange={setSalary}
          />
        </div>

        {message && (
          <div
            className={`rounded-md border p-3 text-sm font-body ${
              message.type === "success"
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-rose-200 bg-rose-50 text-rose-700"
            }`}
          >
            {message.text}
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 rounded-md bg-gold-400 px-4 py-2.5 text-sm font-display font-bold text-navy-900 hover:bg-gold-300 focus:outline-none focus:ring-2 focus:ring-gold-400/50 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save Preferences"}
          </button>
          <button
            onClick={handleUnsubscribe}
            className="rounded-md border border-slate-300 px-4 py-2.5 text-sm font-body text-slate-600 hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-300/50"
          >
            Unsubscribe
          </button>
        </div>
      </div>
    </main>
  );
}
