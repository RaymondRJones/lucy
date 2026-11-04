import type { Config } from "tailwindcss";

// Text tokens meet WCAG AA (4.5:1) on canvas, surface, and paper backgrounds.
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: "#f6f5f0",
        surface: "#ffffff",
        paper: "#f7f6f1",
        line: "#e3e1d8",
        "line-strong": "#c9c6ba",
        ink: "#1f302d",
        muted: "#56635f",
        mist: "#e3efe8",
        pine: {
          DEFAULT: "#25675d",
          strong: "#1c5249",
          soft: "#e3efe9",
        },
        clay: {
          DEFAULT: "#a8522f",
          soft: "#fbf1ec",
        },
        sand: "#d5b98a",
      },
      boxShadow: {
        panel: "0 1px 2px rgba(31, 48, 45, 0.04), 0 8px 24px rgba(31, 48, 45, 0.06)",
        card: "0 1px 2px rgba(31, 48, 45, 0.05)",
        pop: "0 12px 32px rgba(31, 48, 45, 0.16)",
      },
      fontFamily: {
        display: ["Iowan Old Style", "Palatino Linotype", "Book Antiqua", "Georgia", "serif"],
        body: ["Avenir Next", "Segoe UI", "Helvetica Neue", "Arial", "sans-serif"],
      },
      maxWidth: {
        shell: "80rem",
      },
    },
  },
  plugins: [],
};

export default config;
