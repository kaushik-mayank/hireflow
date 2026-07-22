/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./public/index.html"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"DM Sans"', "system-ui", "sans-serif"],
        mono: ['"DM Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        navy: "#0f1629",
        "navy-2": "#1a2340",
        indigo: "#4f6ef7",
        "indigo-light": "#e8edff",
        amber: "#f59e0b",
        "amber-light": "#fef3c7",
        teal: "#0d9488",
        "teal-light": "#ccfbf1",
        coral: "#ef4444",
        "coral-light": "#fee2e2",
        purple: "#7c3aed",
        "purple-light": "#ede9fe",
        green: "#16a34a",
        "green-light": "#dcfce7",
        "gray-50": "#f9fafb",
        "gray-100": "#f3f4f6",
        "gray-200": "#e5e7eb",
        "gray-400": "#9ca3af",
        "gray-600": "#4b5563",
        "gray-700": "#374151",
        "gray-800": "#1f2937",
      },
      boxShadow: {
        soft: "0 1px 3px rgba(15,22,41,0.06), 0 1px 2px rgba(15,22,41,0.04)",
        card: "0 2px 8px rgba(15,22,41,0.06)",
        lift: "0 8px 24px rgba(15,22,41,0.12)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        "slide-in": { from: { opacity: "0", transform: "translateX(20px)" }, to: { opacity: "1", transform: "translateX(0)" } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: {
        "fade-in": "fade-in 0.4s ease-out both",
        "slide-in": "slide-in 0.3s ease-out both",
      },
    },
  },
  plugins: [],
};
