"use client";

import { useState, useRef, useEffect } from "react";
import { useAuth } from "../components/AuthContext";
import { sendChatMessage } from "@/lib/api";
import { VoiceOrb } from "../components/VoiceOrb";
import { useAudioAnalyser } from "../../hooks/useAudioAnalyser";
import { useVoiceAssistant, VoiceAssistantStatus } from "../../hooks/useVoiceAssistant";

export default function Chat() {
  const { token, setToken } = useAuth();
  const [messages, setMessages] = useState<{ role: string; text: string; ts?: string }[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const { getFrequencies, startAnalyser, stopAnalyser } = useAudioAnalyser();

  const { status, activeStream, manualTrigger, isWakeWordEnabled, setIsWakeWordEnabled } = useVoiceAssistant({
    token,
    onCommandProcessed: (transcription, response) => {
        if (transcription) {
             setMessages((prev) => {
                 const newMsgs = [...prev];
                 const lastMsg = newMsgs[newMsgs.length - 1];
                 if (lastMsg && lastMsg.text === "[Voice Audio]") {
                      lastMsg.text = `[Voice] ${transcription}`;
                 } else {
                      newMsgs.push({ role: "user", text: `[Voice] ${transcription}`, ts: new Date().toLocaleTimeString() });
                 }
                 return newMsgs;
             });
        }
        if (response) {
            setMessages((prev) => [...prev, { role: "assistant", text: response, ts: new Date().toLocaleTimeString() }]);
        }
    },
    getFrequencies
  });

  useEffect(() => {
    if (activeStream) {
      startAnalyser(activeStream);
    } else {
      stopAnalyser();
    }
  }, [activeStream]);

  useEffect(() => {
    if (status === VoiceAssistantStatus.RECORDING_COMMAND) {
        setMessages((prev) => {
            const lastMsg = prev[prev.length - 1];
            if (!lastMsg || lastMsg.text !== "[Voice Audio]") {
                return [...prev, { role: "user", text: "[Voice Audio]", ts: new Date().toLocaleTimeString() }];
            }
            return prev;
        });
    }
  }, [status]);

  const handleSend = async () => {
    if (!input.trim() || !token) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: userMsg, ts: new Date().toLocaleTimeString() }]);
    setLoading(true);
    try {
      const res = await sendChatMessage(token, userMsg);
      if (res.response) {
          setMessages((prev) => [...prev, { role: "assistant", text: res.response, ts: new Date().toLocaleTimeString() }]);
      }
    } catch (err: any) {
      if (err.message && err.message.includes("401")) {
        setToken(null);
        return;
      }
      setMessages((prev) => [...prev, { role: "system", text: "UPLINK FAILURE — BACKEND OFFLINE", ts: new Date().toLocaleTimeString() }]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)]">
      {/* Header */}
      <div className="shrink-0 mb-4 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <div className="w-1 h-1 bg-white rotate-45" />
            <p className="font-mono text-[9px] text-white/40 tracking-[0.3em]">NEURAL INTERFACE // ACTIVE</p>
          </div>
          <h2 className="font-hud text-lg font-bold text-white/90 tracking-widest">AI INTERFACE</h2>
        </div>
        <div className="flex items-center gap-4">
          <button 
            onClick={() => setIsWakeWordEnabled(!isWakeWordEnabled)}
            className={`font-mono text-[9px] tracking-widest px-2 py-1 border transition-colors ${
              isWakeWordEnabled 
                ? 'border-emerald-500/50 text-emerald-400 bg-emerald-500/10' 
                : 'border-white/20 text-white/40 hover:bg-white/5'
            }`}
          >
            WAKE WORD: {isWakeWordEnabled ? 'ON' : 'OFF'}
          </button>
          <div className="w-12 h-12 border border-white/20 bg-white/5 rounded-full overflow-hidden" style={{ clipPath: 'circle(50% at 50% 50%)' }}>
            <VoiceOrb 
              getFrequencies={getFrequencies} 
              onClick={manualTrigger} 
            />
          </div>
          <div className="font-mono text-[9px] text-white/30 border border-white/10 px-3 py-1.5 tracking-widest">
            {messages.length} EXCHANGES
          </div>
        </div>
      </div>

      {/* Message window */}
      <div
        className="flex-1 overflow-y-auto border border-white/15 bg-white/10[0.01] p-5 mb-4 space-y-4 relative"
        style={{ clipPath: 'polygon(0 0, calc(100% - 16px) 0, 100% 16px, 100% 100%, 16px 100%, 0 calc(100% - 16px))' }}
      >
        {/* Corner labels */}
        <div className="absolute top-2 left-3 font-mono text-[8px] text-white/20 tracking-widest">COMMS LOG</div>
        <div className="absolute top-2 right-3 font-mono text-[8px] text-white/20 tracking-widest">ENCRYPTED</div>

        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-full border border-white/20 flex items-center justify-center mb-4 animate-pulse">
              <div className="w-10 h-10 rounded-full border border-white/40 flex items-center justify-center">
                <svg className="w-5 h-5 text-white/60" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
                </svg>
              </div>
            </div>
            <p className="font-hud text-xs text-white/40 tracking-widest">SEÑORITA ONLINE</p>
            <p className="font-mono text-[10px] text-white/25 tracking-wider mt-1">AWAITING INPUT...</p>
            <p className="font-mono text-[9px] text-white/20 mt-3">Try: "Add a task: review report by Friday"</p>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[78%] ${m.role === 'user' ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
              {/* Label */}
              <div className={`flex items-center gap-2 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`w-1 h-1 rotate-45 ${
                  m.role === 'user' ? 'bg-blue-400/60' :
                  m.role === 'system' ? 'bg-red-400/60' : 'bg-white/60'
                }`} />
                <span className="font-mono text-[8px] text-white/30 tracking-widest">
                  {m.role === 'user' ? 'USER' : m.role === 'system' ? '⚠ SYSTEM' : 'SEÑORITA'} // {m.ts}
                </span>
              </div>
              {/* Bubble */}
              <div
                className={`px-4 py-3 text-xs font-mono leading-relaxed ${
                  m.role === 'user'
                    ? 'border border-blue-500/30 bg-blue-500/10 text-blue-200'
                    : m.role === 'system'
                    ? 'border border-red-500/30 bg-red-500/5 text-red-400'
                    : 'border border-white/20 bg-white/5 text-white/80/80'
                }`}
                style={{
                  clipPath: m.role === 'user'
                    ? 'polygon(8px 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%, 0 8px)'
                    : 'polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 8px 100%, 0 calc(100% - 8px))'
                }}
              >
                {m.role === 'assistant' && <span className="text-white/40 mr-1">&gt;&gt;</span>}
                {m.text}
              </div>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="border border-white/20 bg-white/5 px-4 py-3"
              style={{ clipPath: 'polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 8px 100%, 0 calc(100% - 8px))' }}>
              <div className="flex items-center gap-3">
                <div className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <span key={i} className="w-1.5 h-1.5 bg-white/60 rounded-full animate-bounce" style={{ animationDelay: `${i * 150}ms` }} />
                  ))}
                </div>
                <span className="font-mono text-[9px] text-white/40 tracking-widest">PROCESSING...</span>
              </div>
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Input bar */}
      <div className="shrink-0 flex gap-3">
        <div className="flex-1 relative border border-white/20 bg-white/10[0.02] flex items-center"
          style={{ clipPath: 'polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 10px 100%, 0 calc(100% - 10px))' }}>
          <span className="font-mono text-[10px] text-white/40 px-4">&gt;_</span>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
            }}
            placeholder="ENTER COMMAND..."
            rows={1}
            disabled={loading}
            className="flex-1 bg-transparent py-3.5 pr-4 font-mono text-xs text-white/90 placeholder:text-white/20 focus:outline-none resize-none"
          />
        </div>
        <button
          onClick={manualTrigger}
          disabled={loading}
          className={`px-4 font-hud text-[9px] tracking-[0.2em] transition-colors shrink-0 ${
            status === VoiceAssistantStatus.RECORDING_COMMAND ? 'bg-red-500/80 text-white animate-pulse' : 'bg-white/10 text-white/60 hover:bg-white/20'
          }`}
          style={{ clipPath: 'polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 8px 100%, 0 calc(100% - 8px))' }}
          title="Voice Command"
        >
          {status === VoiceAssistantStatus.RECORDING_COMMAND ? 'STOP' : 'MIC'}
        </button>
        <button
          onClick={handleSend}
          disabled={loading || (!input.trim() && status !== VoiceAssistantStatus.RECORDING_COMMAND)}
          className="px-5 font-hud text-[9px] tracking-[0.2em] text-background bg-white hover:bg-cyan-300 disabled:opacity-30 disabled:cursor-not-allowed transition-colors shrink-0"
          style={{ clipPath: 'polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 8px 100%, 0 calc(100% - 8px))' }}
        >
          SEND
        </button>
      </div>
    </div>
  );
}
