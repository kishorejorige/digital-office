/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0b0d1a",
        surface: "#15182b",
        surface2: "#1d2140",
        surface3: "#23264a",
        border: "#2a2f55",
        borderSubtle: "#242846",
        accent: "#a78bfa",
        accentHover: "#8b5cf6",
        accentMuted: "rgba(167, 139, 250, 0.12)",
        textPrimary: "#e5e7eb",
        textSecondary: "#9ca3af",
        success: "#22c55e",
        warning: "#f59e0b",
        danger: "#ef4444",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
    },
  },
  plugins: [],
}
