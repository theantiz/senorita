"use client";

import { useEffect, useState } from "react";
import { useAuth } from "../components/AuthContext";
import { getMemories, deleteMemory, patchMemoryLock, MemoryFilters } from "@/lib/api";

export default function Memory() {
  const { token } = useAuth();
  const [memories, setMemories] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters state
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [category, setCategory] = useState<string | undefined>();
  const [sourceRef, setSourceRef] = useState<string | undefined>();
  const [locked, setLocked] = useState<boolean | undefined>();
  const [dateFrom, setDateFrom] = useState<string>("");
  const [dateTo, setDateTo] = useState<string>("");

  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Debounce search
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search);
    }, 500);
    return () => clearTimeout(handler);
  }, [search]);

  async function load() {
    if (!token) return;
    setLoading(true);
    const filters: MemoryFilters = {
      search: debouncedSearch || undefined,
      category,
      source_ref: sourceRef,
      locked,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    };
    const data = await getMemories(token, filters).catch(() => []);
    setMemories(data);
    setLoading(false);
  }

  useEffect(() => { load(); }, [token, debouncedSearch, category, sourceRef, locked, dateFrom, dateTo]);

  const handleToggleLock = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setMemories((prev) => prev.map((m) => m.id === id ? { ...m, locked: !m.locked } : m));
    await patchMemoryLock(token!, id).catch(() => load());
  };

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!confirm("CONFIRM: DELETE THIS MEMORY RECORD?")) return;
    await deleteMemory(token!, id);
    setMemories((prev) => prev.filter((m) => m.id !== id));
  };

  const toggleExpand = (id: string) => {
    setExpandedId(prev => prev === id ? null : id);
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
      preference: "text-blue-400 border-blue-400/30",
      fact: "text-violet-400 border-violet-400/30",
      relationship: "text-emerald-400 border-emerald-400/30",
    };
    return map[cat?.toLowerCase()] ?? "text-white/60 border-white/20";
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="hud-kicker mb-1">// LONG-TERM MEMORY CORE</p>
          <h2 className="hud-title">MEMORY BANK</h2>
        </div>
        <div className="hud-counter w-fit">
          {memories.length} RECORDS
        </div>
      </div>

      {/* Filters */}
      <div className="hud-panel-quiet flex flex-col gap-4 p-4 md:flex-row">
        <div className="flex-1">
          <input 
            type="text" 
            placeholder="SEMANTIC SEARCH..." 
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="hud-input w-full"
          />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <select 
            value={category || ""} 
            onChange={(e) => setCategory(e.target.value || undefined)}
            className="hud-select"
          >
            <option value="">ALL CATEGORIES</option>
            <option value="personal">PERSONAL</option>
            <option value="preference">PREFERENCE</option>
            <option value="fact">FACT</option>
            <option value="relationship">RELATIONSHIP</option>
            <option value="date">DATE</option>
          </select>

          <select 
            value={sourceRef || ""} 
            onChange={(e) => setSourceRef(e.target.value || undefined)}
            className="hud-select"
          >
            <option value="">ALL SOURCES</option>
            <option value="chat">CHAT</option>
            <option value="gmail">GMAIL</option>
            <option value="slack">SLACK</option>
            <option value="implicit_capture">IMPLICIT</option>
          </select>

          <select 
            value={locked === undefined ? "" : locked ? "true" : "false"} 
            onChange={(e) => {
              const val = e.target.value;
              setLocked(val === "" ? undefined : val === "true");
            }}
            className="hud-select"
          >
            <option value="">LOCK STATE: ANY</option>
            <option value="true">LOCKED ONLY</option>
            <option value="false">UNLOCKED ONLY</option>
          </select>

          <div className="flex items-center gap-2 border border-white/20 bg-black/40 px-2">
            <span className="font-mono text-[9px] text-white/50">FROM:</span>
            <input type="date" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="bg-transparent text-white font-mono text-[9px] py-2 focus:outline-none" />
          </div>
          <div className="flex items-center gap-2 border border-white/20 bg-black/40 px-2">
            <span className="font-mono text-[9px] text-white/50">TO:</span>
            <input type="date" value={dateTo} onChange={e => setDateTo(e.target.value)} className="bg-transparent text-white font-mono text-[9px] py-2 focus:outline-none" />
          </div>
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-3 py-8 justify-center">
          <div className="w-4 h-4 border border-[rgba(255,255,255,0.2)] border-t-transparent rounded-full animate-spin" />
          <span className="font-mono text-[10px] text-white/40 tracking-widest">QUERYING MEMORY CORE...</span>
        </div>
      )}

      {!loading && memories.length === 0 && (
        <div className="hud-empty">[ NO RESULTS FOUND ]</div>
      )}

      <div className="space-y-6">
        {dates.map((date) => (
          <div key={date}>
            {/* Date header */}
            <div className="flex items-center gap-3 mb-3">
              <div className="w-1 h-1 bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/60 rotate-45" />
              <p className="font-mono text-[9px] text-white/40 tracking-widest">
                {new Date(date).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' }).toUpperCase()}
              </p>
              <div className="flex-1 h-px bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/10" />
            </div>

            <div className="space-y-2">
              {grouped[date].map((m) => {
                const isExpanded = expandedId === m.id;
                const srcBadge = (m.source_ref ?? "chat").split(":")[0].toUpperCase();
                
                return (
                  <div key={m.id} className="hud-panel-quiet hud-cut-sm flex flex-col transition-colors hover:border-white/25" style={{ clipPath: 'polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 0 100%)' }}>
                    <div 
                      className={`group flex cursor-pointer flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:gap-4 ${m.locked ? 'bg-amber-900/10 border-l-2 border-l-amber-500/50' : ''}`}
                      onClick={() => toggleExpand(m.id)}
                    >
                      {/* Category */}
                      <span className={`font-mono text-[8px] border px-2 py-0.5 tracking-widest shrink-0 ${categoryColor(m.category)}`}>
                        {(m.category ?? 'UNKNOWN').toUpperCase()}
                      </span>

                      {/* Content */}
                      <p className={`min-w-0 flex-1 font-mono text-[11px] leading-relaxed transition-colors ${m.locked ? 'text-amber-100/90' : 'text-white/80 group-hover:text-white'}`}>
                        {m.content}
                      </p>
                      
                      <div className="flex flex-wrap items-center gap-2 lg:contents">
                      {/* Source Badge */}
                      <span className="font-mono text-[8px] text-white/40 border border-white/20 px-1.5 py-0.5">
                        SRC: {srcBadge}
                      </span>

                      {/* Confidence Score */}
                      {m.confidence != null && (
                        <div className="shrink-0 flex items-center gap-1.5" title="Confidence Score">
                          <span className="font-mono text-[8px] text-white/30">CONF</span>
                          <div className="h-1 w-8 bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/10">
                            <div className="h-full bg-blue-400/50" style={{ width: `${m.confidence * 100}%` }} />
                          </div>
                        </div>
                      )}
                      
                      {/* Importance Score */}
                      {m.importance_score != null && (
                        <div className="shrink-0 flex items-center gap-1.5" title="Importance Score">
                          <span className="font-mono text-[8px] text-white/30">IMP</span>
                          <div className="h-1 w-8 bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/10">
                            <div className="h-full bg-violet-400/50" style={{ width: `${m.importance_score * 100}%` }} />
                          </div>
                        </div>
                      )}

                      {/* Lock toggle */}
                      <button
                        onClick={(e) => handleToggleLock(e, m.id)}
                        className={`shrink-0 font-mono text-[8px] border px-2 py-0.5 tracking-widest transition-colors ${
                          m.locked
                            ? 'border-amber-500/50 text-amber-500 bg-amber-500/10 hover:bg-amber-500/20'
                            : 'border-white/15 text-white/30 hover:border-white/50 hover:text-white/80'
                        }`}
                      >
                        {m.locked ? 'LOCKED' : 'LOCK'}
                      </button>

                      {/* Delete */}
                      <button
                        onClick={(e) => handleDelete(e, m.id)}
                        className="shrink-0 font-mono text-[8px] border border-red-500/20 text-red-500/40 px-2 py-0.5 tracking-widest hover:border-red-400/50 hover:text-red-400 transition-colors"
                      >
                        PURGE
                      </button>
                      </div>
                    </div>

                    {/* Expanded Detail */}
                    {isExpanded && (
                      <div className="px-4 py-3 border-t border-white/10 bg-black/20 font-mono text-[9px] text-white/60 space-y-2">
                        <div className="flex justify-between">
                          <span><strong>ID:</strong> {m.id}</span>
                          <span><strong>CREATED:</strong> {new Date(m.created_at).toLocaleString()}</span>
                        </div>
                        <div>
                          <strong>RAW SOURCE REF:</strong> {m.source_ref || "None (Explicit Chat Memory)"}
                        </div>
                        
                        {m.source_ref && m.source_ref.includes(':') && (
                          <div className="pt-2">
                            <a 
                              href={`#link-to-${m.source_ref.replace(':','-')}`} 
                              className="inline-block border border-blue-500/30 text-blue-400 px-3 py-1 hover:bg-blue-500/10"
                              onClick={(e) => e.stopPropagation()}
                            >
                              VIEW ORIGINAL CONVERSATION
                            </a>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
