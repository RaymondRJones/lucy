import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        paper: "#f5efe3",
        ink: "#1f302d",
        mist: "#dbe9e1",
        clay: "#c46b48",
        pine: "#25675d",
        sand: "#d5b98a",
      },
      boxShadow: {
        panel: "0 24px 60px rgba(31, 48, 45, 0.12)",
      },
      fontFamily: {
        display: ["Iowan Old Style", "Palatino Linotype", "Book Antiqua", "Georgia", "serif"],
        body: ["Avenir Next", "Segoe UI", "Helvetica Neue", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
