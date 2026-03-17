import { useEffect, useState } from "react";
import { useParams, Link } from "react-router";
import { confirmSubscription } from "../lib/api";

export function SubscribeConfirm() {
  const { token } = useParams<{ token: string }>();
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("Missing confirmation token.");
      return;
    }
    confirmSubscription(token)
      .then((res) => {
        setStatus("success");
        setMessage(res.message);
      })
      .catch((err) => {
        setStatus("error");
        setMessage(err instanceof Error ? err.message : "Confirmation failed.");
      });
  }, [token]);

  return (
    <main className="mx-auto max-w-md px-6 py-20 text-center">
      {status === "loading" && (
        <div className="flex justify-center py-8" role="status">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-navy-200 border-t-navy-600" />
          <span className="sr-only">Confirming...</span>
        </div>
      )}

      {status === "success" && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-8">
          <svg className="mx-auto h-12 w-12 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <h1 className="mt-4 font-display text-xl font-bold text-emerald-800">{message}</h1>
          <p className="mt-2 font-body text-sm text-emerald-700">
            You'll receive your first weekly digest soon.
          </p>
          <Link
            to="/"
            className="mt-4 inline-block text-sm font-body text-gold-600 hover:text-gold-700 underline"
          >
            Browse jobs now
          </Link>
        </div>
      )}

      {status === "error" && (
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-8">
          <h1 className="font-display text-xl font-bold text-rose-800">Confirmation failed</h1>
          <p className="mt-2 font-body text-sm text-rose-700">{message}</p>
          <Link
            to="/subscribe"
            className="mt-4 inline-block text-sm font-body text-gold-600 hover:text-gold-700 underline"
          >
            Try subscribing again
          </Link>
        </div>
      )}
    </main>
  );
}
