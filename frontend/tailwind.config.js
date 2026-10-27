/** Design tokens live as CSS variables in src/index.css (light + dark); Tailwind maps to them. */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        paper: v("paper"), panel: v("panel"), sunk: v("sunk"),
        ink: v("ink"), "ink-2": v("ink-2"), muted: v("muted"), line: v("line"),
        approve: v("approve"), reject: v("reject"), flag: v("flag"),
        "approve-tint": v("approve-tint"), "reject-tint": v("reject-tint"), "flag-tint": v("flag-tint"),
      },
      fontFamily: {
        sans: ['"Schibsted Grotesk"', "ui-sans-serif", "system-ui", "sans-serif"],
        stamp: ['"Barlow Condensed"', '"Arial Narrow"', "sans-serif"],
      },
      borderRadius: { DEFAULT: "6px" },
    },
  },
  plugins: [],
};
