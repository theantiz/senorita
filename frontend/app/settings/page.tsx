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
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 ease-out">
      <div>
        <h1 className="text-3xl font-display font-semibold text-white tracking-tight">Settings</h1>
        <p className="text-white/50 mt-2 text-sm max-w-xl leading-relaxed">
          Configure global system preferences and default AI behaviors.
        </p>
      </div>

      <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-2xl p-6">
        <h2 className="text-sm font-semibold tracking-wide text-white uppercase mb-4">Default Message Mode</h2>
        <p className="text-white/50 text-sm mb-6">
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
                className={`p-4 rounded-xl border text-left transition-all ${
                  currentModeValue === m.id
                    ? "border-[#4A90E2]/50 bg-[#4A90E2]/10"
                    : "border-white/5 bg-white/5 hover:border-white/20"
                } ${saving ? "opacity-50 cursor-not-allowed" : ""}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className={`font-semibold text-sm ${currentModeValue === m.id ? "text-[#4A90E2]" : "text-white"}`}>
                    {m.title}
                  </span>
                  {currentModeValue === m.id && (
                    <span className="w-2 h-2 rounded-full bg-[#4A90E2]" />
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
