import { createBrowserRouter, RouterProvider, Outlet, Link } from "react-router";
import { Home } from "./routes/home";
import { JobDetail } from "./routes/job-detail";
import { Subscribe } from "./routes/subscribe";
import { SubscribeConfirm } from "./routes/subscribe-confirm";
import { Preferences } from "./routes/preferences";
import { CapitolLogo } from "./components/capitol-art";

function Layout() {
  return (
    <div className="min-h-screen bg-slate-50 font-body text-slate-900">
      <header className="border-b border-navy-800 bg-navy-950">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3">
          <Link to="/" className="group flex items-center gap-2 text-white">
            <CapitolLogo className="h-7 w-7 text-gold-400" />
            <span className="font-display text-xl font-bold tracking-tight">Hill Jobs</span>
          </Link>
          <nav className="hidden items-center gap-6 text-sm font-body text-navy-200 sm:flex">
            <Link to="/" className="transition-colors hover:text-white">
              Find Jobs
            </Link>
            <Link to="/subscribe" className="transition-colors hover:text-white">
              Subscribe to Job Alerts
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
      { path: "/subscribe", element: <Subscribe /> },
      { path: "/subscribe/confirm/:token", element: <SubscribeConfirm /> },
      { path: "/preferences/:token", element: <Preferences /> },
    ],
  },
]);

export function App() {
  return <RouterProvider router={router} />;
}
