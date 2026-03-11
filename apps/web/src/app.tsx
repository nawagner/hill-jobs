import { createBrowserRouter, RouterProvider, Outlet, Link } from "react-router";
import { Home } from "./routes/home";
import { JobDetail } from "./routes/job-detail";

function Layout() {
  return (
    <div className="min-h-screen bg-slate-50 font-body text-slate-900">
      <header className="border-b border-navy-800 bg-navy-950">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <Link to="/" className="flex items-center gap-2 text-white">
            <svg className="h-7 w-7 text-gold-400" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M12 2L2 8v2h20V8L12 2zm0 2.5L18.5 8h-13L12 4.5zM4 12v7a2 2 0 002 2h12a2 2 0 002-2v-7h-2v7H6v-7H4z" />
              <path d="M8 12h2v5H8zM11 12h2v5h-2zM14 12h2v5h-2z" />
            </svg>
            <span className="font-display text-xl font-bold tracking-tight">Hill Jobs</span>
          </Link>
          <nav className="hidden items-center gap-6 text-sm font-body text-navy-200 sm:flex">
            <Link to="/" className="transition-colors hover:text-white">
              Find Jobs
            </Link>
          </nav>
        </div>
      </header>
      <Outlet />
      <footer className="bg-navy-950 py-8 mt-auto">
        <div className="mx-auto max-w-5xl px-6 text-center text-xs text-navy-300 font-body">
          <p>
            A project by{" "}
            <a
              href="https://www.learningjourneyai.com/"
              className="text-gold-400 hover:text-gold-300 transition-colors"
              target="_blank"
              rel="noopener noreferrer"
            >
              Learning Journey AI
            </a>
          </p>
          <p className="mt-2 flex items-center justify-center gap-2">
            <span>Hill Jobs aggregates public job postings from legislative branch employers.</span>
            <span className="text-navy-600">·</span>
            <a
              href="https://github.com/nawagner/hill-jobs"
              className="text-gold-400 hover:text-gold-300 transition-colors"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub
            </a>
            <span className="text-navy-600">·</span>
            <a
              href="mailto:nwagner@learningjourneyai.com"
              className="text-gold-400 hover:text-gold-300 transition-colors"
            >
              Contact us
            </a>
          </p>
        </div>
      </footer>
    </div>
  );
}

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: "/", element: <Home /> },
      { path: "/jobs/:slug", element: <JobDetail /> },
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
