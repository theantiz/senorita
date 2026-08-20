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
        border: "rgba(255,255,255,0.09)",
        input: "rgba(255,255,255,0.05)",
        ring: "hsl(var(--ring))",
        background: "#070b14",
        foreground: "hsl(var(--foreground))",
        glass: "rgba(255,255,255,0.05)",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "rgba(255,255,255,0.05)",
          foreground: "hsl(var(--card-foreground))",
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
