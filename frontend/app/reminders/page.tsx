"use client";

import { useEffect, useState } from "react";
import { useAuth } from "../components/AuthContext";
import { getReminders } from "@/lib/api";

export default function Reminders() {
  const { token } = useAuth();
  const [reminders, setReminders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      if (!token) return;
      const data = await getReminders(token).catch(() => []);
      setReminders(data);
      setLoading(false);
    }
    load();
  }, [token]);

  const activeReminders = reminders.filter((r) => r.status === "pending");
  const pastReminders = reminders.filter((r) => r.status !== "pending");

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <p className="font-mono text-[9px] text-white/40 tracking-[0.3em] mb-1">// ALERT SUBSYSTEM</p>
          <h2 className="font-hud text-lg font-bold text-white/90 tracking-widest">SCHEDULED ALERTS</h2>
        </div>
        <div className="font-mono text-[9px] text-white/30 border border-white/10 px-3 py-1.5 tracking-widest">
          {activeReminders.length} ACTIVE
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-3 py-8 justify-center">
          <div className="w-4 h-4 border border-[rgba(255,255,255,0.2)] border-t-transparent rounded-full animate-spin" />
          <span className="font-mono text-[10px] text-white/40 tracking-widest">CALIBRATING ALERTS...</span>
        </div>
      )}

      {!loading && reminders.length === 0 && (
        <div className="text-center py-12 border border-white/10">
          <p className="font-mono text-[10px] text-white/30 tracking-widest">[ NO ALERTS SCHEDULED ]</p>
        </div>
      )}

      {!loading && reminders.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {activeReminders.map((r) => (
            <div
              key={r.id}
              className="border border-white/20 bg-white/10[0.03] p-4 relative"
              style={{ clipPath: 'polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 0 100%)' }}
            >
              <div className="absolute top-0 right-0 p-3">
                <div className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
              </div>
              <p className="font-mono text-[11px] text-white/80 mb-2 mr-6">{r.message}</p>
              <div className="flex items-center gap-2">
                <span className="font-mono text-[9px] text-white/60 bg-white/10 border border-white/20 px-2 py-1">
                  {new Date(r.trigger_time).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                </span>
                <span className="font-mono text-[8px] text-white/40 tracking-widest">PENDING</span>
              </div>
            </div>
          ))}

          {pastReminders.map((r) => (
            <div
              key={r.id}
              className="border border-white/10 bg-white/10[0.01] p-4 opacity-60"
              style={{ clipPath: 'polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 0 100%)' }}
            >
              <p className="font-mono text-[10px] text-white/60 mb-2">{r.message}</p>
              <div className="flex items-center gap-2">
                <span className="font-mono text-[8px] text-white/30">
                  {new Date(r.trigger_time).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                </span>
                <span className={`font-mono text-[7px] tracking-widest px-1.5 py-0.5 border ${
                  r.status === 'sent' ? 'border-green-500/30 text-green-500/60' : 'border-red-500/30 text-red-500/60'
                }`}>
                  {r.status.toUpperCase()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
