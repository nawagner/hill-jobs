import { useEffect, useState, type CSSProperties } from "react";

// Line drawing of the U.S. Capitol's west front (Senate wing on the left,
// House wing on the right). Each stroke draws itself once per page load;
// afterwards only the chamber flags keep moving. Animations live in
// styles.css and are switched off for prefers-reduced-motion.

// The dome's proportions are measured from "Dome of the U.S. Capitol" (1897),
// https://www.loc.gov/item/96524735/, scaled so the peristyle is 172 units wide.
const CX = 500;

const range = (start: number, end: number, step: number) =>
  Array.from({ length: Math.floor((end - start) / step) + 1 }, (_, i) => start + i * step);

const verticals = (xs: number[], top: number, bottom: number) =>
  xs.map((x) => `M${x} ${bottom}V${top}`).join("");

const windows = (xs: number[], top: number, height: number, width = 5) =>
  xs.map((x) => `M${x} ${top}h${width}v${height}h${-width}Z`).join("");

const rad = (deg: number) => (deg * Math.PI) / 180;
const f = (n: number) => Number(n.toFixed(2));

// Seen from the ground, horizontal rings curve down toward their ends
const sag = (hw: number) => hw * 0.04;
const sagAt = (hw: number, deg: number) => sag(hw) * Math.sin(rad(deg)) ** 2;

// A horizontal ring of half-width hw at height y
const ring = (y: number, hw: number) =>
  `M${f(CX - hw)} ${f(y + sag(hw))}Q${CX} ${f(y - sag(hw))} ${f(CX + hw)} ${f(y + sag(hw))}`;

// A cylindrical band between two heights, with its side edges
const band = (bottom: number, top: number, hw: number) =>
  ring(bottom, hw) +
  ring(top, hw) +
  [CX - hw, CX + hw].map((x) => `M${f(x)} ${f(bottom + sag(hw))}V${f(top + sag(hw))}`).join("");

// Azimuths (0 = facing the viewer) of `count` evenly spaced features on the
// front half of a cylinder; they crowd together toward its edges
const azimuths = (count: number) => Array.from({ length: count }, (_, i) => -90 + (180 / count) * (i + 0.5));

const colonnade = (count: number, hw: number, bottom: number, top: number) =>
  azimuths(count)
    .map((deg) => {
      const x = CX + hw * Math.sin(rad(deg));
      return `M${f(x)} ${f(bottom + sagAt(hw, deg))}V${f(top + sagAt(hw, deg))}`;
    })
    .join("");

// Round-headed windows around a cylinder, narrowing toward its edges
const windowRow = (count: number, hw: number, bottom: number, top: number, width: number) =>
  azimuths(count)
    .map((deg) => {
      const x = CX + hw * Math.sin(rad(deg));
      const rx = (width * Math.cos(rad(deg))) / 2;
      const ry = width / 2;
      const k = sagAt(hw, deg);
      return `M${f(x - rx)} ${f(bottom + k)}V${f(top + ry + k)}A${f(rx)} ${f(ry)} 0 0 1 ${f(x + rx)} ${f(top + ry + k)}V${f(bottom + k)}`;
    })
    .join("");

// The dome shell: a low half-ellipse cut off by the ring the lantern stands on
const DOME_BASE = 192;
const DOME_TOP = 134;
const DOME_RX = 61;
const DOME_RY = 62;
const domeHalfWidth = (y: number) => DOME_RX * Math.sqrt(1 - ((DOME_BASE - y) / DOME_RY) ** 2);
const DOME_TOP_HW = domeHalfWidth(DOME_TOP);

// A dome rib at azimuth `deg`, from the base to the lantern ring
function rib(deg: number) {
  const s = Math.sin(rad(deg));
  if (Math.abs(s) < 0.01) return `M${CX} ${DOME_BASE}V${DOME_TOP}`;
  return `M${f(CX + DOME_RX * s)} ${DOME_BASE}A${f(DOME_RX * Math.abs(s))} ${DOME_RY} 0 0 ${deg < 0 ? 1 : 0} ${f(CX + DOME_TOP_HW * s)} ${DOME_TOP}`;
}

// Statue of Freedom: robed figure with a shield at her side and a feathered
// helmet, standing on a globe (x offsets from the center line, y)
const STATUE_OUTLINE: [number, number][] = [
  [-3.2, 69.8], [-3.3, 66.5], [-3, 63], [-2.6, 60.6], [-3, 58.8], [-2.5, 56.6], [-1.3, 55.8],
  [-1, 54.9], [-1.3, 53.9], [-1.2, 52.9], [-1.9, 51.6], [-0.6, 50.5], [0.9, 50.7], [1.6, 51.8],
  [1.2, 52.9], [1.3, 53.9], [1, 54.9], [1.3, 55.8], [2.6, 56.6], [3.1, 58.4], [3.9, 59.6],
  [4.4, 62.4], [4, 65.2], [3.4, 66.6], [3.3, 69.8],
];
const STATUE_PATH =
  STATUE_OUTLINE.map(([dx, y], i) => `${i ? "L" : "M"}${f(CX + dx)} ${y}`).join("") + "Z";

type Stroke = { d: string; delay: number; dur: number; detail?: boolean; className?: string };

// Drawn bottom to top: terrace, wings, porticos, dome, lantern, statue
const STROKES: Stroke[] = [
  // Ground and terrace
  { d: "M20 410H980M50 410V386H950V410", delay: 0, dur: 0.6 },
  // Main story, cornice and roof balustrade
  { d: "M70 386V330H930V386M62 330H938M70 330V322H930V330", delay: 0.1, dur: 0.8 },
  // Windows between the porticos
  {
    d: windows([...range(84, 152, 17), ...range(268, 422, 17), ...range(573, 727, 17), ...range(846, 914, 17)], 344, 20),
    delay: 0.35,
    dur: 0.8,
    detail: true,
  },
  // Portico columns: Senate wing, center, House wing
  {
    d: verticals([...range(174, 246, 12), ...range(454, 546, 13), ...range(754, 826, 12)], 334, 384),
    delay: 0.35,
    dur: 0.8,
    detail: true,
  },
  // Pediments
  { d: "M164 322L210 304L256 322M446 322L500 302L554 322M744 322L790 304L836 322", delay: 0.55, dur: 0.5 },
  // Dome plinth, peristyle base and entablature
  { d: "M430 322V291H570V322" + ring(290, 88) + band(255.5, 248, 88), delay: 0.65, dur: 0.6 },
  // Peristyle: 36 columns around, 18 facing the viewer
  { d: colonnade(18, 84, 289, 256), delay: 0.8, dur: 0.7, detail: true },
  // Balustrade, attic (drum) and the stepped base of the dome
  {
    d: band(246, 236, 85) + band(234, 209.5, 72.5) + band(209.5, 205.5, 75.5) + band(205.5, 198, 69.5) + band(198, DOME_BASE, 64),
    delay: 0.95,
    dur: 0.6,
  },
  // Attic windows
  { d: windowRow(12, 72.5, 231, 214, 5), delay: 1.05, dur: 0.6, detail: true },
  // Dome outline, flat on top where the lantern stands
  {
    d: `M${CX - DOME_RX} ${DOME_BASE}A${DOME_RX} ${DOME_RY} 0 0 1 ${f(CX - DOME_TOP_HW)} ${DOME_TOP}H${f(CX + DOME_TOP_HW)}A${DOME_RX} ${DOME_RY} 0 0 1 ${CX + DOME_RX} ${DOME_BASE}`,
    delay: 1.15,
    dur: 0.8,
  },
  // Ribs, and the bands framing the row of dome windows
  {
    d: range(-75, 75, 15).map(rib).join("") + ring(180, domeHalfWidth(180)) + ring(161, domeHalfWidth(161)),
    delay: 1.35,
    dur: 0.8,
    detail: true,
  },
  // Dome windows between the ribs
  { d: windowRow(12, domeHalfWidth(171), 177, 165, 3.4), delay: 1.45, dur: 0.6, detail: true },
  // Lantern (tholos): base ring, colonnade and entablature
  { d: band(134, 124, 16.5) + colonnade(6, 13, 123.5, 103) + band(103, 97, 16), delay: 1.75, dur: 0.5 },
  // Bell-shaped bronze cap, pedestal and globe
  {
    d: "M489 97C491.5 90 496.5 84 497.5 76.5H502.5C503.5 84 508.5 90 511 97M494.5 97C496 90 498.3 84 498.8 76.5M505.5 97C504 90 501.7 84 501.2 76.5" +
      "M497.6 76.5V74H502.4V76.5M498 71.8A2 2 0 1 1 502 71.8A2 2 0 1 1 498 71.8",
    delay: 1.95,
    dur: 0.4,
  },
  // Statue of Freedom, and the sword at her right side
  { d: `${STATUE_PATH}M${CX - 3.4} 60.2L${CX - 3.9} 67.2`, delay: 2.15, dur: 0.4, className: "capitol-statue" },
  // Flagpoles over the Senate and House chambers
  { d: "M210 304V250M790 304V250", delay: 0.9, dur: 0.4 },
];

// Flag shapes for one ripple cycle. Every frame has the same path commands,
// so SMIL can interpolate between them.
const FLAG_W = 30;
const FLAG_H = 18;
const FLAG_FRAMES = 6;

function flagFrame(phase: number) {
  // The cloth ripples more the farther it is from the pole
  const dy = (x: number) => 1.8 * (x / FLAG_W) * Math.sin((2 * Math.PI * x) / FLAG_W - phase);
  const pt = (x: number, y: number) => `${x.toFixed(1)} ${(y + dy(x)).toFixed(2)}`;
  const step = FLAG_W / 6;
  // A wavy horizontal line at height y from x0 to x1
  const line = (y: number, x0: number, x1: number) =>
    range(x0, x1, step).map((x, i) => `${i ? "L" : "M"}${pt(x, y)}`).join("");
  const cantonW = FLAG_W / 3;
  const cantonH = (FLAG_H * 7) / 13;
  const bottomEdge = range(0, FLAG_W, step).reverse().map((x) => `L${pt(x, FLAG_H)}`).join("");
  return {
    outline: `${line(0, 0, FLAG_W)}${bottomEdge}Z`,
    // Stripe boundaries: two beside the canton, two full width below it
    stripes: [3, 5].map((k) => line((FLAG_H * k) / 13, cantonW, FLAG_W)).join("") +
      [9, 11].map((k) => line((FLAG_H * k) / 13, 0, FLAG_W)).join(""),
    canton: `${line(0, 0, cantonW)}L${pt(cantonW, cantonH)}L${pt(0, cantonH)}Z`,
  };
}

const FLAG_KEYFRAMES = range(0, FLAG_FRAMES, 1).map((i) => flagFrame((2 * Math.PI * i) / FLAG_FRAMES));
const flagValues = (part: "outline" | "stripes" | "canton") => FLAG_KEYFRAMES.map((f) => f[part]).join(";");

function Flag({ x, y, ripple }: { x: number; y: number; ripple: boolean }) {
  const first = FLAG_KEYFRAMES[0];
  const parts = [
    { part: "canton" as const, className: "capitol-flag-canton" },
    { part: "outline" as const, className: "capitol-flag-outline" },
    { part: "stripes" as const, className: "capitol-flag-stripes" },
  ];
  return (
    <g transform={`translate(${x} ${y})`}>
      <g className="capitol-flag">
        {parts.map(({ part, className }) => (
          <path key={part} d={first[part]} className={className}>
            {ripple && <animate attributeName="d" values={flagValues(part)} dur="2.4s" repeatCount="indefinite" />}
          </path>
        ))}
      </g>
    </g>
  );
}

const prefersReducedMotion = () =>
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;

// The drawing animates on the first visit to the home page; returning to it
// from a job page shows the finished drawing.
let heroHasPlayed = false;

export function CapitolHeroArt({ className = "" }: { className?: string }) {
  const [animate] = useState(() => !heroHasPlayed);
  const [ripple] = useState(() => !prefersReducedMotion());

  useEffect(() => {
    heroHasPlayed = true;
  }, []);

  return (
    <svg
      viewBox="0 0 1000 420"
      preserveAspectRatio="xMidYMax meet"
      className={`capitol-art ${animate ? "" : "is-static"} ${className}`}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <radialGradient id="capitol-glint-glow">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.9" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </radialGradient>
      </defs>
      <g fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round">
        {STROKES.map(({ d, delay, dur, detail, className = "" }, i) => (
          <path
            key={i}
            d={d}
            pathLength={1}
            className={`capitol-stroke ${detail ? "capitol-detail" : ""} ${className}`}
            style={{ "--delay": `${delay}s`, "--dur": `${dur}s` } as CSSProperties}
          />
        ))}
      </g>
      <Flag x={210} y={250} ripple={ripple} />
      <Flag x={790} y={250} ripple={ripple} />
      <circle className="capitol-glint-glow" cx={500} cy={53.5} r={11} fill="url(#capitol-glint-glow)" />
      <path
        className="capitol-glint-star"
        d="M500 43.5L501.1 52.4L510 53.5L501.1 54.6L500 63.5L498.9 54.6L490 53.5L498.9 52.4Z"
        fill="currentColor"
      />
    </svg>
  );
}

// Small dome (24x24) for the header logo and loading indicators
const DOME_ICON_STROKES: Stroke[] = [
  { d: "M3 21H21M5 21V17H19V21M8 21V18.5M12 21V18.5M16 21V18.5", delay: 0, dur: 0.5 },
  { d: "M7.5 17V14H16.5V17M8 14C8 9.5 10 7.5 12 7.5C14 7.5 16 9.5 16 14", delay: 0.3, dur: 0.6 },
  { d: "M11 7.5V5.6H13V7.5M11.3 5.6Q12 4.3 12.7 5.6M12 4.6V2.8", delay: 0.75, dur: 0.3 },
];

const LOGO_GLINT_PATH = "M12 0.4L12.6 2.4L14.6 3L12.6 3.6L12 5.6L11.4 3.6L9.4 3L11.4 2.4Z";

// Header logo: draws itself on page load and glints on hover
export function CapitolLogo({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={`capitol-logo ${className}`} aria-hidden="true" focusable="false">
      <g fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        {DOME_ICON_STROKES.map(({ d, delay, dur }, i) => (
          <path
            key={i}
            d={d}
            pathLength={1}
            className="capitol-stroke"
            style={{ "--delay": `${delay}s`, "--dur": `${dur}s` } as CSSProperties}
          />
        ))}
      </g>
      {/* Separate stars for the glint after drawing and the glint on hover */}
      <path className="capitol-logo-glint" d={LOGO_GLINT_PATH} fill="currentColor" />
      <path className="capitol-logo-glint-hover" d={LOGO_GLINT_PATH} fill="currentColor" />
    </svg>
  );
}

// Loading indicator: the small dome drawing and erasing itself in a loop
export function CapitolLoader({ label, className = "" }: { label: string; className?: string }) {
  return (
    <div role="status" className={`flex justify-center ${className}`}>
      <svg viewBox="0 0 24 24" className="capitol-loader h-10 w-10 text-navy-500" aria-hidden="true" focusable="false">
        <path
          d={DOME_ICON_STROKES.map((s) => s.d).join("")}
          pathLength={1}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.25"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <span className="sr-only">{label}</span>
    </div>
  );
}
