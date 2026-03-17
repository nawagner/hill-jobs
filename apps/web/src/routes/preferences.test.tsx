import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { Preferences } from "./preferences";

afterEach(() => {
  vi.restoreAllMocks();
});

function mockPreferencesFetch() {
  vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;

    if (url.includes("/api/subscribe/preferences/token-123")) {
      return Promise.resolve(new Response(JSON.stringify({
        email: "reader@example.com",
        filters: { committee: "finance-tax" },
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
});
