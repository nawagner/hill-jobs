import { useEffect, useState } from "react";
import { useParams, Link } from "react-router";
import type { JobDetail as JobDetailType } from "../lib/api";
import { getJob, formatDate, formatRoleKind, formatSalary, getEmployerDisplay } from "../lib/api";
import { StatusBadge } from "../components/status-badge";

export function JobDetail() {
  const { slug } = useParams<{ slug: string }>();
  const [job, setJob] = useState<JobDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    getJob(slug)
      .then(setJob)
      .catch(() => setError("Unable to load this position."))
      .finally(() => setLoading(false));
  }, [slug]);

  if (loading) {
    return (
      <div className="flex justify-center py-32">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-navy-200 border-t-navy-600" />
      </div>
    );
  }

  if (error || !job) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16 text-center">
        <h1 className="font-display text-2xl font-bold text-slate-900">Position Not Found</h1>
        <p className="mt-2 text-sm text-slate-500 font-body">{error || "This job may have been removed."}</p>
        <Link to="/" className="mt-6 inline-block text-sm font-medium text-navy-700 hover:text-navy-500 font-body">
          &larr; Back to search
        </Link>
      </main>
    );
  }

  const { employer, office } = getEmployerDisplay(job);

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <Link
        to="/"
        className="inline-flex items-center gap-1 text-sm font-medium text-navy-600 hover:text-navy-800 font-body transition-colors mb-8"
      >
        <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M17 10a.75.75 0 01-.75.75H5.612l4.158 3.96a.75.75 0 11-1.04 1.08l-5.5-5.25a.75.75 0 010-1.08l5.5-5.25a.75.75 0 111.04 1.08L5.612 9.25H16.25A.75.75 0 0117 10z"
            clipRule="evenodd"
          />
        </svg>
        Back to search
      </Link>

      {/* Header */}
      <header className="mb-8">
        <div className="flex items-start gap-3 mb-3">
          <h1 className="font-display text-3xl font-bold text-navy-900 leading-tight md:text-4xl">
            {job.title}
          </h1>
          <StatusBadge status={job.status} />
        </div>
        <p className="text-lg text-slate-600 font-body">{employer}</p>
        {office && <p className="text-sm text-slate-400 font-body mt-1">{office}</p>}
      </header>

      {/* Metadata */}
      <dl className="grid grid-cols-2 gap-x-8 gap-y-4 rounded-lg border border-slate-200 bg-slate-50/50 p-5 mb-8 text-sm font-body sm:grid-cols-4">
        {job.role_kind && (
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">Category</dt>
            <dd className="mt-1 font-medium text-slate-700">{formatRoleKind(job.role_kind)}</dd>
          </div>
        )}
        {job.location_text && (
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">Location</dt>
            <dd className="mt-1 font-medium text-slate-700">{job.location_text}</dd>
          </div>
        )}
        <div>
          <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">Salary</dt>
          <dd className={`mt-1 font-medium ${job.salary_min != null ? "text-slate-700" : "text-slate-400"}`}>
            {formatSalary(job)}
          </dd>
        </div>
        {job.posted_at && (
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">Posted</dt>
            <dd className="mt-1 font-medium text-slate-700">{formatDate(job.posted_at)}</dd>
          </div>
        )}
        {job.closing_at && (
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wider text-slate-400">Closes</dt>
            <dd className="mt-1 font-medium text-slate-700">{formatDate(job.closing_at)}</dd>
          </div>
        )}
      </dl>

      {/* Description */}
      <div
        className="prose prose-slate max-w-none font-body prose-headings:font-display prose-headings:text-navy-900 prose-a:text-navy-600 prose-a:no-underline hover:prose-a:underline"
        dangerouslySetInnerHTML={{ __html: job.description_html }}
      />

      {/* CTA */}
      <div className="mt-10 flex flex-col items-start gap-4 rounded-lg border border-gold-200 bg-gold-50/50 p-6">
        <p className="text-sm text-slate-600 font-body">
          Interested in this position? Apply directly on the original posting.
        </p>
        <a
          href={job.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-md bg-navy-800 px-5 py-2.5 text-sm font-semibold text-white font-body transition-colors hover:bg-navy-700 focus:outline-none focus:ring-2 focus:ring-navy-600 focus:ring-offset-2"
        >
          View Original Posting
          <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M4.25 5.5a.75.75 0 00-.75.75v8.5c0 .414.336.75.75.75h8.5a.75.75 0 00.75-.75v-4a.75.75 0 011.5 0v4A2.25 2.25 0 0112.75 17h-8.5A2.25 2.25 0 012 14.75v-8.5A2.25 2.25 0 014.25 4h5a.75.75 0 010 1.5h-5zm7.25-.75a.75.75 0 01.75-.75h3.5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0V6.31l-5.47 5.47a.75.75 0 01-1.06-1.06l5.47-5.47H12.25a.75.75 0 01-.75-.75z"
              clipRule="evenodd"
            />
          </svg>
        </a>
      </div>
    </main>
  );
}
