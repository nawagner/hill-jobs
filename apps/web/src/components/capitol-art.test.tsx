import { render, screen } from "@testing-library/react";
import { CapitolHeroArt, CapitolLoader } from "./capitol-art";

const commands = (d: string) => d.replace(/[^A-Za-z]/g, "");

describe("CapitolHeroArt", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("is decorative, and draws itself only on the first visit", () => {
    const first = render(<CapitolHeroArt />);
    const svg = first.container.querySelector("svg")!;
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).not.toHaveClass("is-static");
    first.unmount();

    // Coming back to the home page shows the finished drawing
    const second = render(<CapitolHeroArt />);
    expect(second.container.querySelector("svg")).toHaveClass("is-static");
  });

  it("ripples the flags with keyframes SMIL can interpolate", () => {
    const { container } = render(<CapitolHeroArt />);
    const animations = container.querySelectorAll("animate");
    expect(animations.length).toBe(6); // outline, stripes and canton of two flags
    for (const animate of animations) {
      const frames = animate.getAttribute("values")!.split(";");
      expect(frames.length).toBeGreaterThan(2);
      expect(new Set(frames.map(commands)).size).toBe(1);
    }
  });

  it("keeps the flags still when the user prefers reduced motion", () => {
    vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("reduce") }));
    const { container } = render(<CapitolHeroArt />);
    expect(container.querySelectorAll("animate")).toHaveLength(0);
  });
});

describe("CapitolLoader", () => {
  it("announces its label as a status", () => {
    render(<CapitolLoader label="Loading jobs..." />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading jobs...");
  });
});
