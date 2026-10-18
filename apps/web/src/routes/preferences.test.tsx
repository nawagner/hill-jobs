import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { Preferences } from "./preferences";

afterEach(() => {
  vi.restoreAllMocks();
});

function mockPreferencesFetch(filters: Record<string, string> = { committee: "finance-tax" }) {
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;

    if (url.includes("/api/subscribe/preferences/token-123") && init?.method === "PUT") {
      return Promise.resolve(new Response(JSON.stringify({ message: "Preferences updated." })));
    }

    if (url.includes("/api/subscribe/preferences/token-123")) {
      return Promise.resolve(new Response(JSON.stringify({
        email: "reader@example.com",
        filters,
      })));
    }

    if (url.includes("/api/organizations")) {
      return Promise.resolve(new Response(JSON.stringify([])));
    }

    if (url.includes("/api/role-kinds")) {
      return Promise.resolve(new Response(JSON.stringify([])));
    }

    if (url.includes("/api/states")) {
      return Promise.resolve(new Response(JSON.stringify([])));
    }

    if (url.includes("/api/committees")) {
      return Promise.resolve(new Response(JSON.stringify([
        {
          id: "finance",
          name: "Finance",
          chamber: "senate",
          subcommittees: [
            {
              id: "finance-tax",
              name: "Taxation and IRS Oversight",
              chamber: "senate",
              subcommittees: [],
            },
          ],
        },
      ])));
    }

    return Promise.resolve(new Response("not found", { status: 404 }));
  });
}

describe("Preferences", () => {
  it("restores saved subcommittee filters into the visible committee controls", async () => {
    mockPreferencesFetch();

    render(
      <MemoryRouter initialEntries={["/preferences/token-123"]}>
        <Routes>
          <Route path="/preferences/:token" element={<Preferences />} />
        </Routes>
      </MemoryRouter>,
    );

    await screen.findByText("Subscription Preferences");

    await waitFor(() => {
      expect(screen.getByLabelText("Committee")).toHaveValue("finance");
      expect(screen.getByLabelText("Subcommittee")).toHaveValue("finance-tax");
      expect(screen.getByLabelText("Subcommittee")).not.toBeDisabled();
    });
  });

  it("restores and saves the date posted choice", async () => {
    mockPreferencesFetch({ party: "D", freshness: "30" });

    render(
      <MemoryRouter initialEntries={["/preferences/token-123"]}>
        <Routes>
          <Route path="/preferences/:token" element={<Preferences />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByLabelText("Posted within")).toHaveValue("30");
    });
    // Alerts are about recent jobs, so the older-than-30-days option is left out.
    expect(screen.queryByRole("option", { name: "Older than 30 days" })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Posted within"), { target: { value: "7" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Preferences" }));

    await screen.findByText("Preferences updated.");

    const [, init] = vi.mocked(fetch).mock.calls.find(
      ([, init]) => init?.method === "PUT",
    )!;
    expect(JSON.parse(String(init?.body)).filters).toEqual({ party: "D", freshness: "7" });
  });
});
