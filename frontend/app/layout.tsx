import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { AuthProvider } from "./components/AuthContext";
import { AppWrapper } from "./components/AppWrapper";

export const metadata: Metadata = {
  title: "SEÑORITA // OS",
  description: "Intelligent Personal AI Assistant",
};

const navItems = [
  {
    href: "/dashboard", label: "OVERVIEW", code: "01",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-4 h-4">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6A2.25 2.25 0 016 3.75h2.25A2.25 2.25 0 0110.5 6v2.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25V6zM3.75 15.75A2.25 2.25 0 016 13.5h2.25a2.25 2.25 0 012.25 2.25V18a2.25 2.25 0 01-2.25 2.25H6A2.25 2.25 0 013.75 18v-2.25zM13.5 6a2.25 2.25 0 012.25-2.25H18A2.25 2.25 0 0120.25 6v2.25A2.25 2.25 0 0118 10.5h-2.25a2.25 2.25 0 01-2.25-2.25V6zM13.5 15.75a2.25 2.25 0 012.25-2.25H18a2.25 2.25 0 012.25 2.25V18A2.25 2.25 0 0118 20.25h-2.25A2.25 2.25 0 0113.5 18v-2.25z" />
      </svg>
    ),
  },
  {
    href: "/chat", label: "INTERFACE", code: "02",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-4 h-4">
        <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" />
      </svg>
    ),
  },
  {
    href: "/tasks", label: "TASKS", code: "03",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-4 h-4">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    href: "/reminders", label: "ALERTS", code: "04",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-4 h-4">
        <path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
      </svg>
    ),
  },
  {
    href: "/calendar", label: "SCHEDULE", code: "05",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-4 h-4">
        <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5" />
      </svg>
    ),
  },
  {
    href: "/memory", label: "MEMORY", code: "06",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-4 h-4">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 9h16.5m-16.5 6.75h16.5" />
      </svg>
    ),
  },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#070b14] text-white flex overflow-hidden">
        <AuthProvider>
          <AppWrapper>
            {/* ── SIDEBAR ── */}
            <aside className="w-56 shrink-0 flex flex-col border-r border-[rgba(255,255,255,0.09)] bg-[#070b14] relative hidden md:flex">
              {/* Brand */}
              <div className="px-6 pt-8 pb-8">
                <div className="mb-2">
                  <span className="inline-block w-2 h-2 bg-white rounded-full mr-2" />
                  <span className="font-mono text-[10px] text-white/50 tracking-widest uppercase">SYS_ONLINE</span>
                </div>
                <h1 className="font-display text-lg font-semibold tracking-wide text-white">
                  SEÑORITA
                </h1>
              </div>

              {/* Nav */}
              <nav className="flex-1 px-4 space-y-1">
                {navItems.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="group flex items-center gap-3 px-3 py-2 text-white/50 hover:text-white hover:bg-[rgba(255,255,255,0.03)] transition-all duration-200"
                  >
                    <span className="font-mono text-[10px] text-white/30 group-hover:text-white/50 w-4">{item.code}</span>
                    <span className="text-white/40 group-hover:text-white transition-colors">{item.icon}</span>
                    <span className="font-sans text-xs tracking-wide group-hover:text-white">{item.label}</span>
                  </Link>
                ))}
              </nav>

              {/* Bottom diagnostics panel */}
              <div className="mx-4 mb-6 p-4 bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)]">
                <p className="font-mono text-[10px] text-white/50 tracking-widest mb-3 uppercase">Status</p>
                {[
                  { label: "Core", pct: 92 },
                  { label: "Memory", pct: 67 },
                  { label: "Uplink", pct: 100 },
                ].map((d) => (
                  <div key={d.label} className="mb-2 last:mb-0">
                    <div className="flex justify-between mb-1">
                      <span className="font-sans text-xs text-white/60">{d.label}</span>
                      <span className="font-mono text-[10px] text-white/40">{d.pct}%</span>
                    </div>
                    <div className="h-[2px] bg-[rgba(255,255,255,0.05)] w-full">
                      <div className="h-full bg-white/40" style={{ width: `${d.pct}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </aside>

            {/* ── MAIN CONTENT ── */}
            <main className="flex-1 flex flex-col min-h-screen overflow-hidden bg-[#070b14] relative">
              {/* Subtle background grid pattern */}
              <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none" />

              {/* Top status bar */}
              <div className="shrink-0 flex items-center justify-between px-8 py-4 border-b border-[rgba(255,255,255,0.05)] bg-[#070b14]/80 backdrop-blur z-20">
                <div className="flex items-center gap-6">
                  <span className="font-mono text-[10px] text-white/50 tracking-widest uppercase">System Interface</span>
                </div>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-white/80 rounded-full animate-pulse" />
                    <span className="font-mono text-[10px] text-white/50 uppercase tracking-wider">Sync Active</span>
                  </div>
                </div>
              </div>

              {/* Page content */}
              <div className="flex-1 overflow-y-auto relative z-10">
                <div className="max-w-5xl mx-auto px-8 py-8">
                  {children}
                </div>
              </div>
            </main>
          </AppWrapper>
        </AuthProvider>
      </body>
    </html>
  );
}
