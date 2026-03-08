import { Link } from "react-router";
import type { JobListItem } from "../lib/api";
import { formatDate, formatRoleKind, getEmployerDisplay } from "../lib/api";
import { StatusBadge } from "./status-badge";

const roleColors: Record<string, string> = {
  policy: "bg-blue-50 text-blue-700 border-blue-200",
  communications: "bg-violet-50 text-violet-700 border-violet-200",
  legal: "bg-rose-50 text-rose-700 border-rose-200",
  operations: "bg-slate-50 text-slate-600 border-slate-200",
  technology: "bg-cyan-50 text-cyan-700 border-cyan-200",
  security: "bg-orange-50 text-orange-700 border-orange-200",
};

export function JobCard({ job }: { job: JobListItem }) {
  const { employer, office } = getEmployerDisplay(job);

  return (
    <article className="group relative bg-white rounded-lg border border-slate-200 p-5 transition-all duration-200 hover:border-navy-300 hover:shadow-md hover:shadow-navy-900/5">
      <div className="flex items-start justify-between gap-3 mb-3">
        <Link
          to={`/jobs/${job.slug}`}
          className="font-display text-lg font-semibold text-navy-900 leading-snug group-hover:text-navy-700 transition-colors"
        >
          {job.title}
          <span className="absolute inset-0" />
        </Link>
        {job.status === "closed" && <StatusBadge status="closed" />}
      </div>

      <p className="text-sm text-slate-600 font-body mb-1">
        {employer}
      </p>
      {office && (
        <p className="text-xs text-slate-400 font-body mb-3">
          {office}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2 text-xs font-body">
        <span
          className={`inline-flex items-center rounded border px-2 py-0.5 font-medium ${
            roleColors[job.role_kind] || roleColors.operations
          }`}
        >
          {formatRoleKind(job.role_kind)}
        </span>

        {job.location_text && (
          <span className="inline-flex items-center gap-1 text-slate-500">
            <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M9.69 18.933l.003.001C9.89 19.02 10 19 10 19s.11.02.308-.066l.002-.001.006-.003.018-.008a5.741 5.741 0 00.281-.145c.186-.1.446-.25.757-.456a13.239 13.239 0 002.309-2.012c1.476-1.6 2.819-3.885 2.819-6.809 0-3.866-3.134-7-7-7s-7 3.134-7 7c0 2.924 1.343 5.209 2.819 6.809a13.239 13.239 0 002.309 2.012 8.399 8.399 0 001.039.6z" clipRule="evenodd" />
            </svg>
            {job.location_text}
          </span>
        )}

        {job.posted_at && (
          <span className="text-slate-400 ml-auto">
            {formatDate(job.posted_at)}
          </span>
        )}
      </div>
    </article>
  );
}
