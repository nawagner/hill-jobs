const variants = {
  open: "bg-emerald-100 text-emerald-800 border-emerald-200",
  closed: "bg-slate-100 text-slate-500 border-slate-200",
  unknown: "bg-amber-50 text-amber-700 border-amber-200",
} as const;

const labels = {
  open: "Open",
  closed: "Closed",
  unknown: "Status Unknown",
} as const;

export function StatusBadge({ status }: { status: "open" | "closed" | "unknown" }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold font-body tracking-wide ${variants[status]}`}
    >
      <span
        className={`mr-1.5 h-1.5 w-1.5 rounded-full ${
          status === "open" ? "bg-emerald-500" : status === "closed" ? "bg-slate-400" : "bg-amber-500"
        }`}
      />
      {labels[status]}
    </span>
  );
}
