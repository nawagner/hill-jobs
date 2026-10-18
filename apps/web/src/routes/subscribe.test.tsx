import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { Subscribe } from "./subscribe";

afterEach(() => {
  vi.restoreAllMocks();
});

function mockSubscribeFetch() {
  vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;

    if (url.includes("/api/subscribe") && init?.method === "POST") {
      return Promise.resolve(new Response(JSON.stringify({
        message: "Subscription filters updated.",
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
      return Promise.resolve(new Response(JSON.stringify([])));
    }

    return Promise.resolve(new Response("not found", { status: 404 }));
  });
}

describe("Subscribe", () => {
  it("shows the API update message for already-confirmed subscribers", async () => {
    mockSubscribeFetch();

    render(
      <MemoryRouter>
        <Subscribe />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "reader@example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Subscribe to Weekly Digest" }));

    await waitFor(() => {
      expect(screen.getByText("Subscription filters updated.")).toBeInTheDocument();
    });

    expect(screen.queryByText("Check your email")).not.toBeInTheDocument();
  });

  it("saves the date posted choice with the other filters", async () => {
    mockSubscribeFetch();

    render(
      <MemoryRouter>
        <Subscribe />
      </MemoryRouter>,
    );

    fireEvent.change(screen.getByLabelText("Email address"), {
      target: { value: "reader@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Posted within"), { target: { value: "30" } });
    fireEvent.click(screen.getByRole("button", { name: "Subscribe to Weekly Digest" }));

    await screen.findByText("Subscription filters updated.");

    const [, init] = vi.mocked(fetch).mock.calls.find(
      ([, init]) => init?.method === "POST",
    )!;
    expect(JSON.parse(String(init?.body)).filters).toEqual({ freshness: "30" });
  });
});
