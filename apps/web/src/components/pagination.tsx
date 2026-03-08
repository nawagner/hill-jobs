interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onPageChange }: PaginationProps) {
  const totalPages = Math.ceil(total / pageSize);
  if (totalPages <= 1) return null;

  return (
    <nav className="flex items-center justify-between border-t border-slate-200 pt-4 mt-6" aria-label="Pagination">
      <p className="text-sm text-slate-500 font-body">
        Showing <span className="font-medium text-slate-700">{(page - 1) * pageSize + 1}</span>
        {" - "}
        <span className="font-medium text-slate-700">{Math.min(page * pageSize, total)}</span>
        {" of "}
        <span className="font-medium text-slate-700">{total}</span> results
      </p>
      <div className="flex gap-2">
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-body font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Previous
        </button>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-body font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Next
        </button>
      </div>
    </nav>
  );
}
