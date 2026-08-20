import type { Config } from "tailwindcss"

const config = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      animation: {
        'spin-slow': 'spin 3s linear infinite',
      },
      colors: {
        background: 'var(--background)',
        surface: 'var(--surface)',
        foreground: 'var(--foreground)',
        primary: 'var(--primary)',
        secondary: 'var(--secondary)',
        accent: 'var(--accent)',
        'surface-glass': 'var(--surface-glass)',
        'surface-clay': 'var(--surface-clay)',
        glow: 'var(--glow)',
        border: 'var(--border)',
        input: 'var(--surface-glass)',
        ring: 'var(--glow)',
        glass: 'var(--surface-glass)',
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        card: {
          DEFAULT: "var(--surface-glass)",
          foreground: "var(--foreground)",
        },
        // Tactical palette aliases
        cyan: {
          DEFAULT: "#00e5ff",
          400: "#18ffff",
          500: "#00b8d4",
          dark: "rgba(0, 229, 255, 0.1)",
        },
      },
      fontFamily: {
        sans: ['var(--font-inter)', 'sans-serif'],
        display: ['var(--font-plus-jakarta-sans)', 'sans-serif'],
        mono: ['var(--font-geist-mono)', 'monospace'],
        hud: ['var(--font-plus-jakarta-sans)', 'sans-serif'],
      },
      borderRadius: {
        lg: "0rem",
        md: "0rem",
        sm: "0rem",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config

export default config
