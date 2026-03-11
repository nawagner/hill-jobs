import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router";
import { JobDetail } from "./job-detail";

const mockJob = {
  slug: "legislative-analyst-senate",
  title: "Legislative Analyst",
  source_organization: "Senate Committee on Finance",
  source_url: "https://careers.senate.gov/jobs/123",
  status: "open" as const,
  role_kind: "policy",
  location_text: "Washington, DC",
  employment_type: "Full-time",
  posted_at: "2026-03-01T00:00:00",
  closing_at: "2026-04-01T00:00:00",
  source_system: "senate-webscribble",
  source_job_id: "123",
  description_html: "<p>We are seeking a qualified legislative analyst.</p>",
  description_text: "We are seeking a qualified legislative analyst.",
};

afterEach(() => {
  vi.restoreAllMocks();
});

function renderWithRoute(job: Omit<typeof mockJob, "status"> & { status: string }) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(job)),
  );
  return render(
    <MemoryRouter initialEntries={[`/jobs/${job.slug}`]}>
      <Routes>
        <Route path="/jobs/:slug" element={<JobDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("JobDetail", () => {
  it("renders job content and source link", async () => {
    renderWithRoute(mockJob);
    await waitFor(() => {
      expect(screen.getByText("Legislative Analyst")).toBeInTheDocument();
      expect(screen.getByText("U.S. Senate")).toBeInTheDocument();
      expect(screen.getByText("Senate Committee on Finance")).toBeInTheDocument();
      expect(screen.getByText(/seeking a qualified legislative analyst/)).toBeInTheDocument();
    });
    const link = screen.getByRole("link", { name: /View Original Posting/i });
    expect(link).toHaveAttribute("href", "https://careers.senate.gov/jobs/123");
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("renders JSON-LD structured data for the job", async () => {
    renderWithRoute(mockJob);
    await waitFor(() => {
      expect(screen.getByText("Legislative Analyst")).toBeInTheDocument();
    });
    const script = document.querySelector('script[type="application/ld+json"]');
    expect(script).not.toBeNull();
    const data = JSON.parse(script!.textContent!);
    expect(data["@context"]).toBe("https://schema.org");
    expect(data["@type"]).toBe("JobPosting");
    expect(data.title).toBe("Legislative Analyst");
    expect(data.datePosted).toBe("2026-03-01T00:00:00");
    expect(data.hiringOrganization.name).toBe("U.S. Senate");
    expect(data.jobLocation.address.addressLocality).toBe("Washington, DC");
    expect(data.url).toBe("https://careers.senate.gov/jobs/123");
  });

  it("sets page title to include job title and employer", async () => {
    renderWithRoute(mockJob);
    await waitFor(() => {
      expect(document.title).toBe("Legislative Analyst at U.S. Senate — Hill Jobs");
    });
  });

  it("marks decorative SVGs as aria-hidden", async () => {
    renderWithRoute(mockJob);
    await waitFor(() => {
      expect(screen.getByText("Legislative Analyst")).toBeInTheDocument();
    });
    const main = screen.getByRole("main");
    const svgs = main.querySelectorAll("svg");
    expect(svgs.length).toBeGreaterThan(0);
    svgs.forEach((svg) => {
      expect(svg).toHaveAttribute("aria-hidden", "true");
    });
  });

  it("shows closed status badge for closed jobs", async () => {
    renderWithRoute({ ...mockJob, status: "closed" });
    await waitFor(() => {
      expect(screen.getByText("Closed")).toBeInTheDocument();
    });
  });
});
