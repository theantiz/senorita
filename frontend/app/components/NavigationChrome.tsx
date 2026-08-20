"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bell,
  Brain,
  CalendarDays,
  CheckCircle2,
  FileText,
  LayoutDashboard,
  Link2,
  MessageSquareText,
  Settings,
  Users,
} from "lucide-react";
import { ConnectionStatus } from "./ConnectionStatus";
import { SidebarLogout } from "./SidebarLogout";

const navItems = [
  { href: "/dashboard", label: "Overview", code: "01", icon: LayoutDashboard },
  { href: "/chat", label: "Interface", code: "02", icon: MessageSquareText },
  { href: "/tasks", label: "Tasks", code: "03", icon: CheckCircle2 },
  { href: "/reminders", label: "Alerts", code: "04", icon: Bell },
  { href: "/calendar", label: "Schedule", code: "05", icon: CalendarDays },
  { href: "/memory", label: "Memory", code: "06", icon: Brain },
  { href: "/documents", label: "Documents", code: "07", icon: FileText },
  { href: "/connections", label: "Connections", code: "08", icon: Link2 },
  { href: "/contacts", label: "Contacts", code: "09", icon: Users },
  { href: "/settings", label: "Settings", code: "10", icon: Settings },
];

export function routeLabel(pathname: string) {
  return navItems.find((item) => pathname.startsWith(item.href))?.label ?? "System";
}

export function NavigationChrome() {
  const pathname = usePathname();

  return (
    <>
      <aside className="relative hidden w-60 shrink-0 flex-col border-r border-white/[0.09] bg-[#070b14] md:flex">
        <div className="px-6 pb-7 pt-7">
          <ConnectionStatus />
          <h1 className="font-display text-lg font-semibold tracking-wide text-white">
            SENORITA
          </h1>
          <p className="mt-1 font-mono text-[9px] uppercase tracking-[0.26em] text-white/25">
            Personal OS
          </p>
        </div>

        <nav className="flex-1 space-y-1 px-4">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`group flex items-center gap-3 px-3 py-2.5 transition-all duration-200 ${
                  active
                    ? "border border-white/10 bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/[0.06] text-white"
                    : "text-white/45 hover:bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/[0.035] hover:text-white"
                }`}
              >
                <span className={`w-4 font-mono text-[10px] ${active ? "text-cyan-400" : "text-white/25 group-hover:text-white/45"}`}>
                  {item.code}
                </span>
                <Icon className={`h-4 w-4 ${active ? "text-white" : "text-white/35 group-hover:text-white/70"}`} strokeWidth={1.7} />
                <span className="font-sans text-xs tracking-wide">
                  {item.label.toUpperCase()}
                </span>
              </Link>
            );
          })}
        </nav>

        <SidebarLogout />

        <div className="mx-4 mb-6 border border-white/[0.05] bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/[0.02] p-4">
          <p className="mb-3 font-mono text-[10px] uppercase tracking-widest text-white/50">
            Status
          </p>
          {[
            { label: "Core", pct: 92 },
            { label: "Memory", pct: 67 },
            { label: "Uplink", pct: 100 },
          ].map((d) => (
            <div key={d.label} className="mb-2 last:mb-0">
              <div className="mb-1 flex justify-between">
                <span className="font-sans text-xs text-white/60">{d.label}</span>
                <span className="font-mono text-[10px] text-white/40">{d.pct}%</span>
              </div>
              <div className="h-[2px] w-full bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/[0.05]">
                <div className="h-full bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/40" style={{ width: `${d.pct}%` }} />
              </div>
            </div>
          ))}
        </div>
      </aside>

      <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-white/10 bg-[#070b14]/95 px-3 py-2 backdrop-blur-xl md:hidden">
        <div className="flex gap-2 overflow-x-auto pb-safe">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-label={item.label}
                aria-current={active ? "page" : undefined}
                className={`flex min-w-16 flex-col items-center gap-1 border px-3 py-2 transition-colors ${
                  active
                    ? "border-white/15 bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/[0.07] text-white"
                    : "border-transparent text-white/45"
                }`}
              >
                <Icon className="h-4 w-4" strokeWidth={1.7} />
                <span className="font-mono text-[8px] uppercase tracking-wider">
                  {item.label.slice(0, 4)}
                </span>
              </Link>
            );
          })}
        </div>
      </nav>
    </>
  );
}
