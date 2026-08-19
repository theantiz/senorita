"use client";

import { useEffect, useState } from "react";
import { useAuth } from "../components/AuthContext";
import { API_BASE } from "@/lib/api";

type MessageMode = {
  id: string;
  scope: string;
  channel: string | null;
  mode: string;
};

export default function SettingsPage() {
  const { token } = useAuth();
  const [globalMode, setGlobalMode] = useState<MessageMode | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!token) return;
    
    async function fetchModes() {
      try {
        const res = await fetch(`${API_BASE}/message-modes?scope=global`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          const modes = await res.json();
          // Find the true global mode (null channel, null contact)
          const gMode = modes.find((m: MessageMode) => m.channel === null);
          if (gMode) setGlobalMode(gMode);
        }
      } catch (e) {
        console.error("Failed to fetch message modes", e);
      } finally {
        setLoading(false);
      }
    }
    
    fetchModes();
  }, [token]);

  const handleModeChange = async (newMode: string) => {
    if (!token) return;
    setSaving(true);
    
    try {
      if (globalMode) {
        // Update
        const res = await fetch(`${API_BASE}/message-modes/${globalMode.id}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({ mode: newMode })
        });
        if (res.ok) {
          setGlobalMode(await res.json());
        }
      } else {
        // Create
        const res = await fetch(`${API_BASE}/message-modes`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({
            scope: "global",
            contact_id: null,
            channel: null,
            mode: newMode
          })
        });
        if (res.ok) {
          setGlobalMode(await res.json());
        }
      }
    } catch (e) {
      console.error("Failed to update message mode", e);
    } finally {
      setSaving(false);
    }
  };

  const currentModeValue = globalMode?.mode || "approval_required";

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700 ease-out">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="hud-kicker mb-1">// SYSTEM POLICY</p>
          <h1 className="hud-title">SETTINGS</h1>
        </div>
        <div className="hud-counter w-fit">
          {saving ? "SAVING" : "READY"}
        </div>
      </div>

      <div className="hud-panel hud-cut-md p-5 md:p-6">
        <h2 className="mb-4 font-mono text-[10px] uppercase tracking-[0.28em] text-white/60">Default Message Mode</h2>
        <p className="mb-6 max-w-2xl text-sm leading-relaxed text-white/50">
          This controls how the assistant behaves when sending messages on your behalf, unless overridden for a specific contact or channel.
        </p>
        
        {loading ? (
          <div className="h-24 flex items-center justify-center">
            <div className="w-5 h-5 border-2 border-white/20 border-t-white/80 rounded-full animate-spin" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { id: "draft_only", title: "Draft Only", desc: "Never sends automatically. Drafts are prepared for you to send manually in the channel's app." },
              { id: "approval_required", title: "Approval Required (Default)", desc: "Drafts messages and waits for your explicit 'yes' in the interface before sending." },
              { id: "trusted", title: "Trusted", desc: "Sends automatically for straightforward requests, asks for approval on ambiguous or sensitive topics." },
              { id: "autonomous", title: "Autonomous", desc: "Always sends automatically without asking for permission. High risk." },
            ].map((m) => (
              <button
                key={m.id}
                onClick={() => handleModeChange(m.id)}
                disabled={saving}
                className={`hud-cut-sm p-4 text-left transition-all ${
                  currentModeValue === m.id
                    ? "border border-cyan-400/50 bg-cyan-400/10"
                    : "border border-white/10 bg-white/[0.03] hover:border-white/25"
                } ${saving ? "opacity-50 cursor-not-allowed" : ""}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className={`font-semibold text-sm ${currentModeValue === m.id ? "text-cyan-300" : "text-white"}`}>
                    {m.title}
                  </span>
                  {currentModeValue === m.id && (
                    <span className="h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_8px_rgba(103,232,249,0.45)]" />
                  )}
                </div>
                <p className="text-xs text-white/50 leading-relaxed">{m.desc}</p>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
