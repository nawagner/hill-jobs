import { useEffect, useState, type CSSProperties } from "react";

// Line drawing of the U.S. Capitol's west front (Senate wing on the left,
// House wing on the right). Each stroke draws itself once per page load;
// afterwards only the chamber flags keep moving. Animations live in
// styles.css and are switched off for prefers-reduced-motion.

const DOME_X = 500;
const DOME_BASE_Y = 178;
const DOME_RX = 60;
const DOME_RY = 86;
const DOME_TOP_Y = DOME_BASE_Y - DOME_RY;

const range = (start: number, end: number, step: number) =>
  Array.from({ length: Math.floor((end - start) / step) + 1 }, (_, i) => start + i * step);

const verticals = (xs: number[], top: number, bottom: number) =>
  xs.map((x) => `M${x} ${bottom}V${top}`).join("");

const windows = (xs: number[], top: number, height: number, width = 5) =>
  xs.map((x) => `M${x} ${top}h${width}v${height}h${-width}Z`).join("");

const archedWindows = (xs: number[], top: number, bottom: number, width = 6) =>
  xs
    .map((x) => `M${x} ${bottom}V${top + width / 2}A${width / 2} ${width / 2} 0 0 1 ${x + width} ${top + width / 2}V${bottom}`)
    .join("");

// A dome meridian at azimuth `deg` (0 = facing the viewer), base to top
function rib(deg: number) {
  const rx = Math.abs(DOME_RX * Math.sin((deg * Math.PI) / 180));
  const x = DOME_X + Math.sign(deg) * rx;
  if (rx < 0.5) return `M${DOME_X} ${DOME_BASE_Y}V${DOME_TOP_Y}`;
  return `M${x} ${DOME_BASE_Y}A${rx} ${DOME_RY} 0 0 ${deg < 0 ? 1 : 0} ${DOME_X} ${DOME_TOP_Y}`;
}

// A horizontal ring around the dome at elevation `deg` above its base
function ring(deg: number) {
  const rad = (deg * Math.PI) / 180;
  const y = DOME_BASE_Y - DOME_RY * Math.sin(rad);
  const half = DOME_RX * Math.cos(rad);
  return `M${DOME_X - half} ${y}Q${DOME_X} ${y + 4} ${DOME_X + half} ${y}`;
}

type Stroke = { d: string; delay: number; dur: number; detail?: boolean };

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
  { d: "M430 322V290H570V322M414 290H586M414 232H586M410 226H590", delay: 0.65, dur: 0.6 },
  // Peristyle columns
  { d: verticals(range(422, 578, 8), 232, 289), delay: 0.8, dur: 0.7, detail: true },
  // Balustrade and attic drum
  { d: "M422 226V219H578V226M438 219V184H562V219M432 184H568M436 184V178H564V184", delay: 0.95, dur: 0.6 },
  // Attic windows
  { d: archedWindows(range(445, 547, 12), 194, 213), delay: 1.05, dur: 0.6, detail: true },
  // Dome outline
  {
    d: `M${DOME_X - DOME_RX} ${DOME_BASE_Y}A${DOME_RX} ${DOME_RY} 0 0 1 ${DOME_X} ${DOME_TOP_Y}A${DOME_RX} ${DOME_RY} 0 0 1 ${DOME_X + DOME_RX} ${DOME_BASE_Y}`,
    delay: 1.15,
    dur: 0.8,
  },
  // Ribs and window rings
  { d: [-60, -38, -18, 0, 18, 38, 60].map(rib).join("") + ring(32) + ring(58), delay: 1.35, dur: 0.8, detail: true },
  // Lantern
  { d: "M488 92V70H512V92M494 90V72M500 90V72M506 90V72M485 70Q500 54 515 70M497 62V57H503V62", delay: 1.8, dur: 0.45 },
  // Statue of Freedom
  { d: "M498 57L499 41Q500 37 501 41L502 57M499 39Q501 32 503.5 35", delay: 2.05, dur: 0.35 },
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
        {STROKES.map(({ d, delay, dur, detail }, i) => (
          <path
            key={i}
            d={d}
            pathLength={1}
            className={`capitol-stroke ${detail ? "capitol-detail" : ""}`}
            style={{ "--delay": `${delay}s`, "--dur": `${dur}s` } as CSSProperties}
          />
        ))}
      </g>
      <Flag x={210} y={250} ripple={ripple} />
      <Flag x={790} y={250} ripple={ripple} />
      <circle className="capitol-glint-glow" cx={500} cy={36} r={16} fill="url(#capitol-glint-glow)" />
      <path
        className="capitol-glint-star"
        d="M500 22L501.5 34.5L514 36L501.5 37.5L500 50L498.5 37.5L486 36L498.5 34.5Z"
        fill="currentColor"
      />
    </svg>
  );
}

// Small dome (24x24) for the header logo and loading indicators
const DOME_ICON_STROKES: Stroke[] = [
  { d: "M3 21H21M5 21V17H19V21M8 21V18.5M12 21V18.5M16 21V18.5", delay: 0, dur: 0.5 },
  { d: "M7.5 17V14H16.5V17M8 14C8 9.5 10 7.5 12 7.5C14 7.5 16 9.5 16 14", delay: 0.3, dur: 0.6 },
  { d: "M11 7.5V5.5H13V7.5M12 5.5V3", delay: 0.75, dur: 0.3 },
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
