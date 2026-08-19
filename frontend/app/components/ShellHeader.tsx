"use client";

import { usePathname } from "next/navigation";
import { routeLabel } from "./NavigationChrome";

export function ShellHeader() {
  const pathname = usePathname();
  const label = routeLabel(pathname);

  return (
    <div className="z-20 flex shrink-0 items-center justify-between border-b border-white/[0.05] bg-[#070b14]/85 px-4 py-3 backdrop-blur md:px-8 md:py-4">
      <div className="min-w-0">
        <span className="font-mono text-[10px] uppercase tracking-widest text-white/50">
          System Interface
        </span>
        <p className="mt-0.5 truncate font-display text-sm font-semibold text-white/80 md:hidden">
          {label}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.45)]" />
        <span className="font-mono text-[10px] uppercase tracking-wider text-white/50">
          Sync Active
        </span>
      </div>
    </div>
  );
}
