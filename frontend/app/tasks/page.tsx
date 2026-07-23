"use client";

import { useEffect, useState } from "react";
import { useAuth } from "../components/AuthContext";
import { getTasks } from "@/lib/api";

export default function Tasks() {
  const { token } = useAuth();
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      if (!token) return;
      const data = await getTasks(token).catch(() => []);
      setTasks(data);
      setLoading(false);
    }
    load();
  }, [token]);

  const openTasks = tasks.filter((t) => !t.completed_at);
  const doneTasks = tasks.filter((t) => t.completed_at);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <p className="font-mono text-[9px] text-white/40 tracking-[0.3em] mb-1">// ACTION ITEM MATRIX</p>
          <h2 className="font-hud text-lg font-bold text-white/90 tracking-widest">TASK QUEUE</h2>
        </div>
        <div className="font-mono text-[9px] text-white/30 border border-white/10 px-3 py-1.5 tracking-widest">
          {openTasks.length} OPEN / {tasks.length} TOTAL
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-3 py-8 justify-center">
          <div className="w-4 h-4 border border-[rgba(255,255,255,0.2)] border-t-transparent rounded-full animate-spin" />
          <span className="font-mono text-[10px] text-white/40 tracking-widest">SYNCING TASK MATRIX...</span>
        </div>
      )}

      {!loading && tasks.length === 0 && (
        <div className="text-center py-12 border border-white/10">
          <p className="font-mono text-[10px] text-white/30 tracking-widest">[ TASK QUEUE EMPTY ]</p>
        </div>
      )}

      {!loading && tasks.length > 0 && (
        <div className="space-y-6">
          {/* Active Tasks */}
          {openTasks.length > 0 && (
            <div className="space-y-3">
              <p className="font-mono text-[9px] text-white/60 tracking-widest flex items-center gap-2 mb-2">
                <span className="w-1.5 h-1.5 bg-white/60 rounded-full animate-pulse-glow" />
                ACTIVE DIRECTIVES
              </p>
              {openTasks.map((t) => (
                <div
                  key={t.id}
                  className="flex items-start gap-4 border border-white/20 bg-white/10[0.03] p-4 group hover:border-white/40 transition-all"
                  style={{ clipPath: 'polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 10px 100%, 0 calc(100% - 10px))' }}
                >
                  <div className="mt-0.5 shrink-0 w-3 h-3 border border-white/40 flex items-center justify-center">
                    <div className="w-1.5 h-1.5 bg-white/20 group-hover:bg-white/60 transition-colors" />
                  </div>
                  <div className="flex-1">
                    <p className="font-mono text-[11px] text-white/80">{t.title}</p>
                    {t.description && (
                      <p className="font-mono text-[9px] text-white/50 mt-1 line-clamp-2">{t.description}</p>
                    )}
                  </div>
                  {t.priority === "high" && (
                    <div className="shrink-0 border border-red-500/30 bg-red-500/10 px-2 py-0.5">
                      <span className="font-mono text-[8px] text-red-400 tracking-widest">PRIORITY: HIGH</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Completed Tasks */}
          {doneTasks.length > 0 && (
            <div className="space-y-3 opacity-60">
              <p className="font-mono text-[9px] text-white/40 tracking-widest flex items-center gap-2 mb-2">
                <span className="w-1.5 h-1.5 bg-white/20 border border-white/40" />
                RESOLVED DIRECTIVES
              </p>
              {doneTasks.map((t) => (
                <div
                  key={t.id}
                  className="flex items-center gap-4 border border-white/10 bg-white/10[0.01] p-3"
                  style={{ clipPath: 'polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%)' }}
                >
                  <div className="shrink-0 w-3 h-3 bg-white/20 border border-white/40 flex items-center justify-center">
                    <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <p className="font-mono text-[10px] text-white/40 line-through decoration-cyan-500/30 flex-1">{t.title}</p>
                  <span className="font-mono text-[7px] text-white/30 tracking-widest">
                    {new Date(t.completed_at).toLocaleDateString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
