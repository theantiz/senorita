"use client";

import { useEffect, useState } from "react";
import { useAuth } from "../components/AuthContext";
import { getMemory, deleteMemory, patchMemoryLock } from "@/lib/api";

export default function Memory() {
  const { token } = useAuth();
  const [memories, setMemories] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    if (!token) return;
    const data = await getMemory(token).catch(() => []);
    setMemories(data);
    setLoading(false);
  }

  useEffect(() => { load(); }, [token]);

  const handleToggleLock = async (id: string) => {
    setMemories((prev) => prev.map((m) => m.id === id ? { ...m, locked: !m.locked } : m));
    await patchMemoryLock(token!, id).catch(() => load());
  };

  const handleDelete = async (id: string) => {
    if (!confirm("CONFIRM: DELETE THIS MEMORY RECORD?")) return;
    await deleteMemory(token!, id);
    setMemories((prev) => prev.filter((m) => m.id !== id));
  };

  const grouped: Record<string, any[]> = {};
  memories.forEach((m) => {
    const d = m.created_at?.split("T")[0] ?? "unknown";
    if (!grouped[d]) grouped[d] = [];
    grouped[d].push(m);
  });
  const dates = Object.keys(grouped).sort((a, b) => b.localeCompare(a));

  const categoryColor = (cat: string) => {
    const map: Record<string, string> = {
      personal: "text-white border-white/30",
      preference: "text-white border-blue-400/30",
      fact: "text-violet-400 border-violet-400/30",
      relationship: "text-emerald-400 border-emerald-400/30",
    };
    return map[cat?.toLowerCase()] ?? "text-white/60 border-white/20";
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <p className="font-mono text-[9px] text-white/40 tracking-[0.3em] mb-1">// LONG-TERM MEMORY CORE</p>
          <h2 className="font-hud text-lg font-bold text-white/90 tracking-widest">MEMORY BANK</h2>
        </div>
        <div className="font-mono text-[9px] text-white/30 border border-white/10 px-3 py-1.5 tracking-widest">
          {memories.length} RECORDS
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-3 py-8 justify-center">
          <div className="w-4 h-4 border border-[rgba(255,255,255,0.2)] border-t-transparent rounded-full animate-spin" />
          <span className="font-mono text-[10px] text-white/40 tracking-widest">LOADING MEMORY CORE...</span>
        </div>
      )}

      {!loading && memories.length === 0 && (
        <div className="text-center py-12 border border-white/10">
          <p className="font-mono text-[10px] text-white/30 tracking-widest">[ MEMORY CORE EMPTY ]</p>
          <p className="font-mono text-[9px] text-white/20 mt-1">CHAT WITH SEÑORITA TO BEGIN BUILDING MEMORY</p>
        </div>
      )}

      <div className="space-y-6">
        {dates.map((date) => (
          <div key={date}>
            {/* Date header */}
            <div className="flex items-center gap-3 mb-3">
              <div className="w-1 h-1 bg-white/60 rotate-45" />
              <p className="font-mono text-[9px] text-white/40 tracking-widest">
                {new Date(date).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' }).toUpperCase()}
              </p>
              <div className="flex-1 h-px bg-white/10" />
            </div>

            <div className="space-y-2">
              {grouped[date].map((m) => (
                <div
                  key={m.id}
                  className="flex items-center gap-4 border border-white/10 bg-white/10[0.02] px-4 py-3 group hover:border-white/25 transition-colors"
                  style={{ clipPath: 'polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%)' }}
                >
                  {/* Category */}
                  <span className={`font-mono text-[8px] border px-2 py-0.5 tracking-widest shrink-0 ${categoryColor(m.category)}`}>
                    {(m.category ?? 'UNKNOWN').toUpperCase()}
                  </span>

                  {/* Content */}
                  <p className="font-mono text-[11px] text-white/80/70 flex-1 group-hover:text-white/80 transition-colors">
                    {m.content}
                  </p>

                  {/* Score */}
                  {m.importance_score != null && (
                    <div className="shrink-0 flex items-center gap-1.5">
                      <div className="h-1 w-12 bg-white/10">
                        <div className="h-full bg-white/50 transition-all" style={{ width: `${m.importance_score * 100}%` }} />
                      </div>
                      <span className="font-mono text-[8px] text-white/30">{Math.round(m.importance_score * 100)}%</span>
                    </div>
                  )}

                  {/* Lock toggle */}
                  <button
                    onClick={() => handleToggleLock(m.id)}
                    className={`shrink-0 font-mono text-[8px] border px-2 py-0.5 tracking-widest transition-colors ${
                      m.locked
                        ? 'border-white/50 text-white bg-white/10'
                        : 'border-white/15 text-white/30 hover:border-white/30'
                    }`}
                  >
                    {m.locked ? '⌛ LOCKED' : '○ LOCK'}
                  </button>

                  {/* Delete */}
                  <button
                    onClick={() => handleDelete(m.id)}
                    className="shrink-0 font-mono text-[8px] border border-red-500/20 text-red-500/40 px-2 py-0.5 tracking-widest hover:border-red-400/50 hover:text-red-400 transition-colors"
                  >
                    PURGE
                  </button>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
