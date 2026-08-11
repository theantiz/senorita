"use client";

import { useEffect, useState, useRef } from "react";
import { useAuth } from "../components/AuthContext";
import { getTasks, getCalendarEvents, getActivity, sendVoiceMessage, getLatestBriefing, getLatestEodBriefing } from "@/lib/api";
import dynamic from "next/dynamic";

const VoiceOrb = dynamic(() => import("../components/VoiceOrb").then(mod => mod.VoiceOrb), { ssr: false });
import { useAudioAnalyser } from "../../hooks/useAudioAnalyser";
import { useVoiceAssistant, VoiceAssistantStatus } from "../../hooks/useVoiceAssistant";

function HudCard({ children, title, code }: { children: React.ReactNode; title: string; code: string }) {
  return (
    <div className="relative border border-white/15 bg-white/10[0.02] p-5" style={{ clipPath: 'polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 0 100%)' }}>
      {/* Top label */}
      <div className="flex items-center justify-between mb-4">
        <p className="font-mono text-[9px] text-white/40 tracking-[0.25em] uppercase">{title}</p>
        <p className="font-mono text-[9px] text-white/20">{code}</p>
      </div>
      {children}
      {/* Corner decoration */}
      <div className="absolute bottom-0 right-0 w-3 h-3 border-b border-r border-white/20" />
    </div>
  );
}

export default function Dashboard() {
  const { token } = useAuth();
  const [tasks, setTasks] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [activities, setActivities] = useState<any[]>([]);
  const [briefing, setBriefing] = useState<any>(null);
  const [eodBriefing, setEodBriefing] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  
  const { isListening: analyserActive, startAnalyser, stopAnalyser, getFrequencies } = useAudioAnalyser();
  
  const { status, voiceResponse, activeStream, manualTrigger, isWakeWordEnabled, setIsWakeWordEnabled } = useVoiceAssistant({
    token,
    onCommandProcessed: loadData,
    getFrequencies
  });

  // Attach analyser to the active stream when recording starts
  useEffect(() => {
    if (activeStream) {
      startAnalyser(activeStream);
    } else {
      stopAnalyser();
    }
  }, [activeStream]);

  const toggleWakeWord = () => {
    setIsWakeWordEnabled(!isWakeWordEnabled);
  };

  async function loadData() {
    if (!token) return;
    const [t, e, a, b, eod] = await Promise.all([
      getTasks(token).catch(() => []),
      getCalendarEvents(token).catch(() => []),
      getActivity(token).catch(() => []),
      getLatestBriefing(token).catch(() => ({ data: null })),
      getLatestEodBriefing(token).catch(() => ({ data: null }))
    ]);
    setTasks(t);
    setEvents(e);
    setActivities(a);
    setBriefing(b?.data || null);
    setEodBriefing(eod?.data || null);
    setLoading(false);
  }

  useEffect(() => {
    loadData();
  }, [token]);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "GOOD MORNING" : hour < 17 ? "GOOD AFTERNOON" : "GOOD EVENING";
  const todayStr = new Date().toISOString().split("T")[0];
  const openTasks = tasks.filter((t) => !t.completed_at);
  const todaysEvents = events.filter((e) => e.start_time?.startsWith(todayStr));
  const actionsToday = activities.filter((a) => a.created_at?.startsWith(todayStr)).length;

  const stats = [
    { label: "OPEN TASKS", value: loading ? "—" : openTasks.length, sub: "PENDING COMPLETION" },
    { label: "SCHEDULED", value: loading ? "—" : todaysEvents.length, sub: "EVENTS TODAY" },
    { label: "ACTIONS", value: loading ? "—" : actionsToday, sub: "HANDLED BY AI" },
  ];

  return (
    <div className="space-y-6">
      {/* AI Voice Assistant Orb */}
      <div className="border border-white/20 bg-white/10[0.01] p-1 relative h-48 md:h-64 flex flex-col justify-end" style={{ clipPath: 'polygon(0 0, calc(100% - 16px) 0, 100% 16px, 100% 100%, 16px 100%, 0 calc(100% - 16px))' }}>
        <div className="absolute inset-0">
          <VoiceOrb 
            getFrequencies={getFrequencies} 
            onClick={manualTrigger}
          />
        </div>
        
        {voiceResponse && (
          <div className="relative z-10 w-full flex justify-center pb-4 pointer-events-none">
            <p className="font-mono text-xs text-white/90 bg-black/60 backdrop-blur-md px-4 py-2 border border-white/20 text-center max-w-[80%] uppercase tracking-widest shadow-[0_0_15px_rgba(255,255,255,0.1)]">
              {voiceResponse}
            </p>
          </div>
        )}
      </div>

      {/* Header */}
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-white/10">
        <div>
          <p className="font-mono text-[9px] text-white/40 tracking-[0.3em] mb-1">
            {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }).toUpperCase()}
          </p>
          <h2 className="font-hud text-xl font-bold text-white/90 tracking-widest text-white">
            {greeting}
          </h2>
        </div>
        <div className="flex items-center gap-6">
          <button 
            onClick={toggleWakeWord}
            className={`font-mono text-[10px] tracking-widest px-3 py-1 border transition-colors ${
              isWakeWordEnabled 
                ? 'border-emerald-500/50 text-emerald-400 bg-emerald-500/10' 
                : 'border-white/20 text-white/40 hover:bg-white/5'
            }`}
          >
            WAKE WORD: {isWakeWordEnabled ? 'ON' : 'OFF'}
          </button>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${status === VoiceAssistantStatus.IDLE_LISTENING ? 'bg-emerald-500 animate-pulse shadow-[0_0_10px_rgba(16,185,129,0.5)]' : status === VoiceAssistantStatus.RECORDING_COMMAND ? 'bg-red-500 animate-pulse shadow-[0_0_10px_rgba(239,68,68,0.5)]' : 'bg-white/20'}`} />
            <span className="font-mono text-[10px] text-white/40 tracking-widest">SYNC ACTIVE</span>
          </div>
        </div>
      </div>

      {/* show the history of today's activities */}
      <div className="grid grid-cols-3 gap-4">
        {stats.map((s) => (
          <div
            key={s.label}
            className="border border-white/20 bg-white/10[0.03] p-5 relative"
            style={{ clipPath: 'polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 10px 100%, 0 calc(100% - 10px))' }}
          >
            <p className="font-mono text-[8px] tracking-[0.25em] mb-2 text-white/40">{s.label}</p>
            <p className="font-hud text-5xl font-bold mb-1 text-white">{s.value}</p>
            <p className="font-mono text-[8px] text-white/30 tracking-widest">{s.sub}</p>
            {/* Corner deco */}
            <div className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full animate-pulse bg-white/40" />
          </div>
        ))}
      </div>

      {/* display the morning and evening briefings side-by-side */}
      <div className="grid grid-cols-2 gap-4">
        <HudCard title="// MORNING BRIEFING" code="BRF-001">
          {loading ? (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 border border-[rgba(255,255,255,0.2)] border-t-transparent rounded-full animate-spin" />
              <span className="font-mono text-[10px] text-white/40">FETCHING DATA...</span>
            </div>
          ) : briefing ? (
            <p className="font-mono text-[11px] text-white/80 leading-relaxed whitespace-pre-wrap">{briefing.content}</p>
          ) : (
            <p className="font-mono text-[10px] text-white/30">[ NO BRIEFING GENERATED YET ]</p>
          )}
        </HudCard>
        
        <HudCard title="// EVENING BRIEFING" code="BRF-002">
          {loading ? (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 border border-[rgba(255,255,255,0.2)] border-t-transparent rounded-full animate-spin" />
              <span className="font-mono text-[10px] text-white/40">FETCHING DATA...</span>
            </div>
          ) : eodBriefing ? (
            <p className="font-mono text-[11px] text-white/80 leading-relaxed whitespace-pre-wrap">{eodBriefing.content}</p>
          ) : (
            <p className="font-mono text-[10px] text-white/30">[ NO BRIEFING GENERATED YET ]</p>
          )}
        </HudCard>
      </div>

      {/* render the main task and calendar panels */}
      <div className="grid grid-cols-2 gap-4">
        {/* Tasks */}
        <HudCard title="// TASK QUEUE" code="TQ-001">
          {loading ? (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 border border-[rgba(255,255,255,0.2)] border-t-transparent rounded-full animate-spin" />
              <span className="font-mono text-[10px] text-white/40">FETCHING DATA...</span>
            </div>
          ) : openTasks.length === 0 ? (
            <p className="font-mono text-[10px] text-white/30">[ QUEUE EMPTY — ALL TASKS RESOLVED ]</p>
          ) : (
            <ul className="space-y-2">
              {openTasks.slice(0, 6).map((t) => (
                <li key={t.id} className="flex items-center gap-2.5 group">
                  <div className="w-1 h-1 bg-white/40 rotate-45 shrink-0 group-hover:bg-white transition-colors" />
                  <span className="font-mono text-[10px] text-white/90/70 group-hover:text-white/80 transition-colors flex-1 truncate">{t.title}</span>
                  {t.priority === 'high' && (
                    <span className="font-mono text-[7px] text-red-400 border border-red-500/30 px-1 py-px shrink-0">HIGH</span>
                  )}
                </li>
              ))}
              {openTasks.length > 6 && (
                <p className="font-mono text-[9px] text-white/30 mt-1">... +{openTasks.length - 6} MORE IN QUEUE</p>
              )}
            </ul>
          )}
        </HudCard>

        {/* Calendar */}
        <HudCard title="// SCHEDULE MATRIX" code="SM-001">
          {loading ? (
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 border border-[rgba(255,255,255,0.2)] border-t-transparent rounded-full animate-spin" />
              <span className="font-mono text-[10px] text-white/40">SYNCING...</span>
            </div>
          ) : todaysEvents.length === 0 ? (
            <p className="font-mono text-[10px] text-white/30">[ NO EVENTS DETECTED TODAY ]</p>
          ) : (
            <ul className="space-y-3">
              {todaysEvents.slice(0, 5).map((e) => (
                <li key={e.id} className="flex gap-3">
                  <div className="shrink-0">
                    <div className="font-mono text-[9px] text-white/60 bg-white/10 border border-white/20 px-2 py-1 text-center">
                      {new Date(e.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                  <div>
                    <p className="font-mono text-[10px] text-white/80/80">{e.title}</p>
                    {e.location && <p className="font-mono text-[9px] text-white/40 mt-0.5">⌖ {e.location}</p>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </HudCard>
      </div>
    </div>
  );
}
