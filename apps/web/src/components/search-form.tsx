import { useState } from "react";

interface SearchFormProps {
  initialQuery: string;
  onSearch: (query: string) => void;
}

export function SearchForm({ initialQuery, onSearch }: SearchFormProps) {
  const [query, setQuery] = useState(initialQuery);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSearch(query);
  }

  return (
    <form onSubmit={handleSubmit} className="flex w-full max-w-2xl gap-0">
      <div className="relative flex-1">
        <svg
          className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
            clipRule="evenodd"
          />
        </svg>
        <input
          type="text"
          name="q"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Job title or keyword"
          className="w-full rounded-l-md border border-r-0 border-slate-300 bg-white py-3 pl-12 pr-4 text-sm font-body text-slate-900 placeholder:text-slate-400 focus:border-gold-400 focus:outline-none focus:ring-2 focus:ring-gold-400/30"
        />
      </div>
      <button
        type="submit"
        className="rounded-r-md bg-gold-500 px-6 py-3 text-sm font-semibold font-body uppercase tracking-wider text-navy-950 transition-colors hover:bg-gold-400 focus:outline-none focus:ring-2 focus:ring-gold-400/50 focus:ring-offset-2"
      >
        Search
      </button>
    </form>
  );
}
