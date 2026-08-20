"use client";

import { useEffect, useState } from "react";
import { useAuth } from "../components/AuthContext";
import { getCalendarEvents } from "@/lib/api";

export default function Calendar() {
  const { token } = useAuth();
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      if (!token) return;
      const data = await getCalendarEvents(token).catch(() => []);
      setEvents(data);
      setLoading(false);
    }
    load();
  }, [token]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="hud-kicker mb-1">// SCHEDULE MATRIX</p>
          <h2 className="hud-title">TEMPORAL LOG</h2>
        </div>
        <div className="hud-counter w-fit">
          {events.length} EVENTS LOADED
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-3 py-8 justify-center">
          <div className="w-4 h-4 border border-[rgba(255,255,255,0.2)] border-t-transparent rounded-full animate-spin" />
          <span className="font-mono text-[10px] text-white/40 tracking-widest">SYNCING MATRIX...</span>
        </div>
      )}

      {!loading && events.length === 0 && (
        <div className="hud-empty">[ NO UPCOMING EVENTS ]</div>
      )}

      {!loading && events.length > 0 && (
        <div className="space-y-3">
          {events.map((e) => (
            <div
              key={e.id}
              className="hud-panel hud-cut-md flex flex-col gap-0 overflow-hidden transition-colors hover:bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/[0.04] sm:flex-row sm:items-stretch sm:gap-4"
              style={{ clipPath: 'polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 0 100%)' }}
            >
              {/* Time column */}
              <div className="shrink-0 border-b border-white/10 bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/[0.05] p-4 text-left sm:w-32 sm:border-b-0 sm:border-r sm:text-center">
                <span className="font-mono text-[11px] text-white">
                  {new Date(e.start_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
                <span className="font-mono text-[8px] text-white/40 mt-1 tracking-widest">
                  {new Date(e.start_at).toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' }).toUpperCase()}
                </span>
              </div>
              
              {/* Event details */}
              <div className="flex-1 p-4">
                <p className="font-mono text-[11px] text-white/80">{e.title}</p>
                {e.description && (
                  <p className="font-mono text-[9px] text-white/60 mt-1 line-clamp-2">{e.description}</p>
                )}
                {e.location && (
                  <div className="mt-2 inline-flex items-center gap-1.5 border border-white/20 bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/10 px-2 py-0.5">
                    <span className="font-mono text-[8px] text-white tracking-widest">LOC: {e.location.toUpperCase()}</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
