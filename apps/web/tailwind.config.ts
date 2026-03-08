import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          50: "#f0f3f8",
          100: "#d9e0ed",
          200: "#b3c1db",
          300: "#8da2c9",
          400: "#6783b7",
          500: "#4a6a9e",
          600: "#3a5580",
          700: "#2a3f61",
          800: "#1B2A4A",
          900: "#162237",
          950: "#0e1624",
        },
        gold: {
          50: "#fdf9ef",
          100: "#faf0d5",
          200: "#f4deaa",
          300: "#edc974",
          400: "#e4af3d",
          500: "#D4A843",
          600: "#b8872a",
          700: "#996624",
          800: "#7d5223",
          900: "#674320",
        },
      },
      fontFamily: {
        display: ['"Cormorant Garamond"', "Georgia", "serif"],
        body: ['"Source Sans 3"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
