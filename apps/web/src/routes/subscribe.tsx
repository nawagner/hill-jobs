import { useEffect, useState, useCallback } from "react";
import type { OrganizationItem, StateItem, CommitteeItem } from "../lib/api";
import { getOrganizations, getRoleKinds, getStates, getCommittees, subscribe } from "../lib/api";
import { Filters } from "../components/filters";

export function Subscribe() {
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

  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getOrganizations(), getRoleKinds(), getStates(), getCommittees()])
      .then(([orgs, kinds, sts, cmts]) => {
        setOrganizations(orgs);
        setRoleKinds(kinds);
        setStates(sts);
        setCommittees(cmts);
      })
      .catch(() => {});
  }, []);

  const handleCommitteeChange = useCallback((value: string) => {
    setCommittee(value);
    setSubcommittee("");
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    const filters: Record<string, string> = {};
    if (roleKind) filters.role_kind = roleKind;
    if (organization) filters.organization = organization;
    if (party) filters.party = party;
    if (state) filters.state = state;
    const effectiveCommittee = subcommittee || committee;
    if (effectiveCommittee) filters.committee = effectiveCommittee;
    if (salary) filters.salary_min = salary;

    try {
      await subscribe(email, filters);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  };

  if (success) {
    return (
      <main className="mx-auto max-w-xl px-6 py-20 text-center">
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-8">
          <svg className="mx-auto h-12 w-12 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 19v-8.93a2 2 0 01.89-1.664l7-4.666a2 2 0 012.22 0l7 4.666A2 2 0 0121 10.07V19M3 19a2 2 0 002 2h14a2 2 0 002-2M3 19l6.75-4.5M21 19l-6.75-4.5M3 10l6.75 4.5M21 10l-6.75 4.5m0 0l-1.14.76a2 2 0 01-2.22 0l-1.14-.76" />
          </svg>
          <h2 className="mt-4 font-display text-xl font-bold text-emerald-800">Check your email</h2>
          <p className="mt-2 font-body text-sm text-emerald-700">
            We sent a confirmation link to <strong>{email}</strong>. Click it to activate your weekly digest.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <div className="text-center mb-8">
        <h1 className="font-display text-3xl font-bold text-navy-900">Weekly Job Alerts</h1>
        <p className="mt-2 font-body text-slate-500">
          Get a weekly email with new positions matching your preferences.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div>
          <label htmlFor="email" className="block text-sm font-body font-medium text-slate-700 mb-1">
            Email address
          </label>
          <input
            id="email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-body text-slate-700 focus:border-gold-400 focus:outline-none focus:ring-2 focus:ring-gold-400/30"
          />
        </div>

        <div>
          <p className="block text-sm font-body font-medium text-slate-700 mb-2">
            Filter preferences
          </p>
          <p className="text-xs font-body text-slate-400 mb-3">
            Leave filters empty to receive all new job postings.
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

        {error && (
          <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 font-body">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-gold-400 px-4 py-2.5 text-sm font-display font-bold text-navy-900 hover:bg-gold-300 focus:outline-none focus:ring-2 focus:ring-gold-400/50 disabled:opacity-50"
        >
          {submitting ? "Subscribing..." : "Subscribe to Weekly Digest"}
        </button>
      </form>
    </main>
  );
}
