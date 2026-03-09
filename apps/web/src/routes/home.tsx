import { useEffect, useState, useCallback } from "react";
import { useSearchParams } from "react-router";
import type { JobSearchResponse, OrganizationItem } from "../lib/api";
import { searchJobs, getOrganizations, getRoleKinds } from "../lib/api";
import { SearchForm } from "../components/search-form";
import { Filters } from "../components/filters";
import { JobCard } from "../components/job-card";
import { Pagination } from "../components/pagination";

export function Home() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [results, setResults] = useState<JobSearchResponse | null>(null);
  const [organizations, setOrganizations] = useState<OrganizationItem[]>([]);
  const [roleKinds, setRoleKinds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const q = searchParams.get("q") || "";
  const roleKind = searchParams.get("role_kind") || "";
  const organization = searchParams.get("organization") || "";
  const freshness = searchParams.get("freshness") || searchParams.get("posted_since_days") || "";
  const page = Number(searchParams.get("page")) || 1;

  const updateParam = useCallback(
    (key: string, value: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value) {
          next.set(key, value);
        } else {
          next.delete(key);
        }
        if (key !== "page") next.delete("page");
        return next;
      });
    },
    [setSearchParams],
  );

  useEffect(() => {
    Promise.all([getOrganizations(), getRoleKinds()])
      .then(([orgs, kinds]) => {
        setOrganizations(orgs);
        setRoleKinds(kinds);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    searchJobs({
      q: q || undefined,
      role_kind: roleKind || undefined,
      organization: organization || undefined,
      posted_since_days: freshness && freshness !== "older_30" ? Number(freshness) : undefined,
      posted_before_days: freshness === "older_30" ? 30 : undefined,
      page,
    })
      .then(setResults)
      .catch(() => setError("Unable to load jobs. Please try again."))
      .finally(() => setLoading(false));
  }, [q, roleKind, organization, freshness, page]);

  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden bg-navy-900 py-16 md:py-24">
        <div
          className="absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage:
              "url(\"data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")",
          }}
        />
        <div className="relative mx-auto max-w-5xl px-6 text-center">
          <h1 className="font-display text-4xl font-bold tracking-tight text-white md:text-5xl lg:text-6xl">
            Your Next Career on
            <br />
            <span className="text-gold-400">the Hill</span> Starts Here
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-base text-navy-200 font-body md:text-lg">
            Search open positions across the Senate, House, Capitol Police,
            Library of Congress, and Architect of the Capitol.
          </p>
          <div className="mt-8 flex justify-center">
            <SearchForm
              initialQuery={q}
              onSearch={(value) => updateParam("q", value)}
            />
          </div>
        </div>
      </section>

      {/* Results */}
      <main className="mx-auto max-w-5xl px-6 py-8">
        <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <Filters
            roleKinds={roleKinds}
            organizations={organizations}
            selectedRoleKind={roleKind}
            selectedOrganization={organization}
            selectedFreshness={freshness}
            onRoleKindChange={(v) => updateParam("role_kind", v)}
            onOrganizationChange={(v) => updateParam("organization", v)}
            onFreshnessChange={(v) => updateParam("freshness", v)}
          />
          {results && !loading && (
            <p className="text-sm text-slate-500 font-body whitespace-nowrap">
              {results.total} {results.total === 1 ? "position" : "positions"} found
            </p>
          )}
        </div>

        {error && (
          <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700 font-body">
            {error}
          </div>
        )}

        {loading && (
          <div className="flex justify-center py-20">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-navy-200 border-t-navy-600" />
          </div>
        )}

        {!loading && results && results.items.length === 0 && (
          <div className="py-20 text-center">
            <p className="text-lg font-display text-slate-400">No positions found</p>
            <p className="mt-1 text-sm text-slate-400 font-body">
              Try broadening your search or adjusting filters.
            </p>
          </div>
        )}

        {!loading && results && results.items.length > 0 && (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              {results.items.map((job) => (
                <JobCard key={job.slug} job={job} />
              ))}
            </div>
            <Pagination
              page={results.page}
              pageSize={results.page_size}
              total={results.total}
              onPageChange={(p) => updateParam("page", String(p))}
            />
          </>
        )}
      </main>

      {/* FAQ */}
      <section className="border-t border-slate-200 bg-white py-12">
        <div className="mx-auto max-w-3xl px-6">
          <h2 className="font-display text-2xl font-bold text-navy-900 mb-6">
            Frequently Asked Questions
          </h2>
          <div className="divide-y divide-slate-200 border-y border-slate-200">
            <details className="group">
              <summary className="flex cursor-pointer items-center justify-between py-4 text-sm font-body font-medium text-slate-700 hover:text-navy-900">
                Where does this data come from?
                <span className="ml-2 text-gold-500 transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="pb-4 text-sm font-body text-slate-500 leading-relaxed">
                Hill Jobs collects publicly posted job listings from the official career
                pages of legislative branch employers, including the U.S. Senate, the
                U.S. House of Representatives, the U.S. Capitol Police, the Library of
                Congress, and the Architect of the Capitol.
              </p>
            </details>
            <details className="group">
              <summary className="flex cursor-pointer items-center justify-between py-4 text-sm font-body font-medium text-slate-700 hover:text-navy-900">
                How often are listings updated?
                <span className="ml-2 text-gold-500 transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="pb-4 text-sm font-body text-slate-500 leading-relaxed">
                Most listings are refreshed daily and typically appear within
                24 hours of being posted on their original career page. House
                positions sourced from the House Employment Bulletin
                are updated weekly.
              </p>
            </details>
            <details className="group">
              <summary className="flex cursor-pointer items-center justify-between py-4 text-sm font-body font-medium text-slate-700 hover:text-navy-900">
                Can I apply for jobs through Hill Jobs?
                <span className="ml-2 text-gold-500 transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="pb-4 text-sm font-body text-slate-500 leading-relaxed">
                No. Hill Jobs is a search tool only. Each listing links directly to the
                original posting where you can review full details and submit your
                application.
              </p>
            </details>
            <details className="group">
              <summary className="flex cursor-pointer items-center justify-between py-4 text-sm font-body font-medium text-slate-700 hover:text-navy-900">
                Is this an official government website?
                <span className="ml-2 text-gold-500 transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="pb-4 text-sm font-body text-slate-500 leading-relaxed">
                No. Hill Jobs is not affiliated with or endorsed by the U.S. Congress or
                any government agency. It is a project
                by{" "}
                <a
                  href="https://www.learningjourneyai.com/"
                  className="text-gold-600 underline hover:text-gold-700"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Learning Journey AI
                </a>.
              </p>
            </details>
          </div>
        </div>
      </section>
    </>
  );
}
