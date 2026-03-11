import { Link } from "react-router";
import type { JobListItem } from "../lib/api";
import { formatDate, formatRoleKind, formatSalary, getEmployerDisplay } from "../lib/api";
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
        <span className="sr-only">Organization: </span>{employer}
      </p>
      {office && (
        <p className="text-xs text-slate-400 font-body mb-3">
          <span className="sr-only">Member: </span>{office}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2 text-xs font-body">
        <span
          className={`inline-flex items-center rounded border px-2 py-0.5 font-medium ${
            roleColors[job.role_kind] || roleColors.operations
          }`}
        >
          <span className="sr-only">Category: </span>{formatRoleKind(job.role_kind)}
        </span>

        {job.location_text && (
          <span className="inline-flex items-center gap-1 text-slate-500">
            <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fillRule="evenodd" d="M9.69 18.933l.003.001C9.89 19.02 10 19 10 19s.11.02.308-.066l.002-.001.006-.003.018-.008a5.741 5.741 0 00.281-.145c.186-.1.446-.25.757-.456a13.239 13.239 0 002.309-2.012c1.476-1.6 2.819-3.885 2.819-6.809 0-3.866-3.134-7-7-7s-7 3.134-7 7c0 2.924 1.343 5.209 2.819 6.809a13.239 13.239 0 002.309 2.012 8.399 8.399 0 001.039.6z" clipRule="evenodd" />
            </svg>
            <span className="sr-only">Location: </span>{job.location_text}
          </span>
        )}

        <span className={`inline-flex items-center gap-1 ${job.salary_min != null ? "text-slate-500" : "text-slate-400"}`}>
          <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
            <path d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.736 6.979C9.208 6.193 9.696 6 10 6c.304 0 .792.193 1.264.979a1 1 0 001.715-1.029C12.279 4.784 11.232 4 10 4s-2.279.784-2.979 1.95c-.285.475-.507 1-.67 1.55H6a1 1 0 000 2h.013a9.358 9.358 0 000 1H6a1 1 0 100 2h.351c.163.55.385 1.075.67 1.55C7.721 15.216 8.768 16 10 16s2.279-.784 2.979-1.95a1 1 0 10-1.715-1.029c-.472.786-.96.979-1.264.979-.304 0-.792-.193-1.264-.979a5.95 5.95 0 01-.342-.521H10a1 1 0 100-2H8.092a7.364 7.364 0 010-1H10a1 1 0 100-2H8.394c.1-.183.21-.357.342-.521z" />
          </svg>
          <span className="sr-only">Salary: </span>{formatSalary(job)}
        </span>

        {job.posted_at && (
          <span className="text-slate-400 ml-auto">
            <span className="sr-only">Posted: </span>{formatDate(job.posted_at)}
          </span>
        )}
      </div>

      {job.member_committees && job.member_committees.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {job.member_committees.slice(0, 3).map((name) => (
            <span
              key={name}
              className="inline-flex items-center rounded bg-amber-50 border border-amber-200 px-1.5 py-0.5 text-[11px] font-body text-amber-700 leading-tight"
              title={name}
            >
              {name.replace(/^(House |Senate )?Committee on /, "")}
            </span>
          ))}
          {job.member_committees.length > 3 && (
            <span className="text-[11px] text-slate-400 font-body py-0.5">
              +{job.member_committees.length - 3} more
            </span>
          )}
        </div>
      )}
    </article>
  );
}
