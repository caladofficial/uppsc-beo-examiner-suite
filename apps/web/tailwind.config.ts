import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        outerSpace: "#484A47",
        paynesGray: "#5C6D70",
        oldRose: "#A37774",
        salmon: "#E88873",
        melon: "#E0AC9D",
        canvasCream: "#FAF6F3",
        linenCard: "#F3ECE7",
      },
      fontFamily: {
        sans: ["Inter", "Noto Sans Devanagari", "system-ui", "sans-serif"],
        serif: ["Georgia", "Noto Serif Devanagari", "serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
