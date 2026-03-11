import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { Home } from "./home";

const mockJobs = {
  items: [
    {
      slug: "chief-of-staff-senate",
      title: "Chief of Staff",
      source_system: "senate-webscribble",
      source_organization: "Office of Sen. Smith",
      source_url: "https://example.com/job/1",
      status: "open" as const,
      role_kind: "policy",
      location_text: "Washington, DC",
      employment_type: null,
      posted_at: "2026-03-01T00:00:00",
      closing_at: null,
      salary_min: null,
      salary_max: null,
      salary_period: null,
      member_committees: null,
    },
    {
      slug: "systems-admin-cao",
      title: "Systems Administrator",
      source_system: "csod-house-cao",
      source_organization: "House CAO",
      source_url: "https://example.com/job/2",
      status: "closed" as const,
      role_kind: "technology",
      location_text: null,
      employment_type: null,
      posted_at: "2026-02-15T00:00:00",
      closing_at: null,
      salary_min: null,
      salary_max: null,
      salary_period: null,
      member_committees: null,
    },
  ],
  total: 2,
  page: 1,
  page_size: 20,
};

function mockFetchResponses() {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : (input as Request).url;
    if (url.includes("/api/jobs?") || url.endsWith("/api/jobs")) {
      return Promise.resolve(new Response(JSON.stringify(mockJobs)));
    }
    if (url.includes("/api/organizations")) {
      return Promise.resolve(new Response(JSON.stringify([
        { name: "House CAO", source_system: "csod-house-cao", party: null },
        { name: "Office of Sen. Smith", source_system: "senate-webscribble", party: null },
      ])));
    }
    if (url.includes("/api/role-kinds")) {
      return Promise.resolve(new Response(JSON.stringify(["policy", "technology"])));
    }
    return Promise.resolve(new Response("not found", { status: 404 }));
  });
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Home", () => {
  it("announces loading state for screen readers", () => {
    mockFetchResponses();
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    const status = screen.getByRole("status");
    expect(status).toBeInTheDocument();
    expect(status).toHaveTextContent(/loading/i);
  });

  it("renders search controls", async () => {
    mockFetchResponses();
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    expect(screen.getByPlaceholderText("Search by title, office, location...")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Search" })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByLabelText("Role category")).toBeInTheDocument();
      expect(screen.getByLabelText("Organization")).toBeInTheDocument();
      expect(screen.getByLabelText("Posted within")).toBeInTheDocument();
      expect(screen.getByLabelText("Salary")).toBeInTheDocument();
    });
  });

  it("renders results with organization and role kind", async () => {
    mockFetchResponses();
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("Chief of Staff")).toBeInTheDocument();
      expect(screen.getByText("U.S. Senate")).toBeInTheDocument();
      expect(screen.getAllByText("Office of Sen. Smith").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Policy").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("Systems Administrator")).toBeInTheDocument();
      expect(screen.getAllByText("U.S. House of Representatives").length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText("Technology").length).toBeGreaterThanOrEqual(1);
    });
  });

  it("includes sr-only labels on job card fields for LLM readability", async () => {
    mockFetchResponses();
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("Chief of Staff")).toBeInTheDocument();
    });
    // Each job card should have labeled fields via sr-only spans
    const articles = screen.getAllByRole("article");
    const first = articles[0];
    expect(first).toHaveTextContent("Organization:");
    expect(first).toHaveTextContent("Category:");
    expect(first).toHaveTextContent("Salary:");
    expect(first).toHaveTextContent("Posted:");
    // Job with location should have location label
    expect(first).toHaveTextContent("Location:");
    // Job with office/member should have member label
    expect(first).toHaveTextContent("Member:");
  });

  it("shows a closed badge for closed jobs", async () => {
    mockFetchResponses();
    render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText("Closed")).toBeInTheDocument();
    });
  });
});
