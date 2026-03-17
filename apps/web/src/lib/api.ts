export interface JobListItem {
  slug: string;
  title: string;
  source_system: string;
  source_organization: string;
  source_url: string;
  status: "open" | "closed" | "unknown";
  role_kind: string;
  location_text: string | null;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_period: string | null;
  posted_at: string | null;
  closing_at: string | null;
  member_committees: string[] | null;
}

export interface JobDetail extends JobListItem {
  source_job_id: string | null;
  description_html: string;
  description_text: string;
}

export interface JobSearchResponse {
  items: JobListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface SearchParams {
  q?: string;
  role_kind?: string;
  organization?: string;
  party?: string;
  state?: string;
  committee?: string;
  posted_since_days?: number;
  posted_before_days?: number;
  salary_min?: number;
  page?: number;
}

export async function searchJobs(params: SearchParams): Promise<JobSearchResponse> {
  const query = new URLSearchParams();
  if (params.q) query.set("q", params.q);
  if (params.role_kind) query.set("role_kind", params.role_kind);
  if (params.organization) query.set("organization", params.organization);
  if (params.party) query.set("party", params.party);
  if (params.state) query.set("state", params.state);
  if (params.committee) query.set("committee", params.committee);
  if (params.posted_since_days) query.set("posted_since_days", String(params.posted_since_days));
  if (params.posted_before_days) query.set("posted_before_days", String(params.posted_before_days));
  if (params.salary_min != null) query.set("salary_min", String(params.salary_min));
  if (params.page && params.page > 1) query.set("page", String(params.page));

  const res = await fetch(`/api/jobs?${query.toString()}`);
  if (!res.ok) throw new Error(`Search failed: ${res.status}`);
  return res.json();
}

export async function getJob(slug: string): Promise<JobDetail> {
  const res = await fetch(`/api/jobs/${encodeURIComponent(slug)}`);
  if (!res.ok) throw new Error(`Job not found: ${res.status}`);
  return res.json();
}

export interface OrganizationItem {
  name: string;
  source_system: string;
  party: string | null;
  state: string | null;
  committees: string[] | null;
}

export interface StateItem {
  code: string;
  name: string;
}

export interface CommitteeItem {
  id: string;
  name: string;
  chamber: string;
  subcommittees: CommitteeItem[];
}

export async function getOrganizations(): Promise<OrganizationItem[]> {
  const res = await fetch("/api/organizations");
  if (!res.ok) throw new Error(`Failed to load organizations: ${res.status}`);
  return res.json();
}

export async function getRoleKinds(): Promise<string[]> {
  const res = await fetch("/api/role-kinds");
  if (!res.ok) throw new Error(`Failed to load role kinds: ${res.status}`);
  return res.json();
}

export async function getStates(): Promise<StateItem[]> {
  const res = await fetch("/api/states");
  if (!res.ok) throw new Error(`Failed to load states: ${res.status}`);
  return res.json();
}

export async function getCommittees(): Promise<CommitteeItem[]> {
  const res = await fetch("/api/committees");
  if (!res.ok) throw new Error(`Failed to load committees: ${res.status}`);
  return res.json();
}

export function formatDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function formatRoleKind(kind: string): string {
  return kind.charAt(0).toUpperCase() + kind.slice(1);
}

const EMPLOYER_NAMES: Record<string, string> = {
  "senate-webscribble": "U.S. Senate",
  "csod-house-cao": "U.S. House of Representatives",
  "csod-uscp": "U.S. Capitol Police",
  "loc-careers": "Library of Congress",
  "aoc-usajobs": "Architect of the Capitol",
  "house-bulletin": "U.S. House of Representatives",
  "house-dems-resumebank": "U.S. House of Representatives",
};

export function formatSalary(job: Pick<JobListItem, "salary_min" | "salary_max" | "salary_period">): string {
  if (job.salary_min == null && job.salary_max == null) {
    return "Unable to find salary";
  }
  const fmt = (n: number) =>
    n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  const period = job.salary_period === "hourly" ? "/hr" : "/yr";
  const min = job.salary_min;
  const max = job.salary_max;
  if (min != null && max != null && min !== max) {
    return `${fmt(min)} – ${fmt(max)} ${period}`;
  }
  const value = min ?? max!;
  return `${fmt(value)} ${period}`;
}

export function getEmployerDisplay(job: Pick<JobListItem, "source_system" | "source_organization">) {
  const employer = EMPLOYER_NAMES[job.source_system] || job.source_organization;
  const office = employer !== job.source_organization ? job.source_organization : null;
  return { employer, office };
}

// --- Subscribe / Newsletter API ---

export interface SubscribeFilters {
  q?: string;
  role_kind?: string;
  organization?: string;
  party?: string;
  state?: string;
  committee?: string;
  salary_min?: string;
}

export async function subscribe(email: string, filters: SubscribeFilters): Promise<{ message: string }> {
  const res = await fetch("/api/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, filters }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Subscribe failed: ${res.status}`);
  }
  return res.json();
}

export async function confirmSubscription(token: string): Promise<{ message: string }> {
  const res = await fetch(`/api/subscribe/confirm/${encodeURIComponent(token)}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Confirmation failed: ${res.status}`);
  }
  return res.json();
}

export async function getPreferences(token: string): Promise<{ email: string; filters: SubscribeFilters }> {
  const res = await fetch(`/api/subscribe/preferences/${encodeURIComponent(token)}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Failed to load preferences: ${res.status}`);
  }
  return res.json();
}

export async function updatePreferences(token: string, filters: SubscribeFilters): Promise<{ message: string }> {
  const res = await fetch(`/api/subscribe/preferences/${encodeURIComponent(token)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filters }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Update failed: ${res.status}`);
  }
  return res.json();
}

export async function unsubscribe(token: string): Promise<{ message: string }> {
  const res = await fetch(`/api/subscribe/unsubscribe/${encodeURIComponent(token)}`, {
    method: "POST",
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `Unsubscribe failed: ${res.status}`);
  }
  return res.json();
}
