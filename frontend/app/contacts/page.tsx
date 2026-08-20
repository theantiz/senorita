"use client";

import { useEffect, useState } from "react";
import { useAuth } from "../components/AuthContext";
import { API_BASE } from "@/lib/api";

type Contact = {
  id: string;
  name: string;
  relationship_type: string;
};

type MessageMode = {
  id: string;
  scope: string;
  contact_id: string | null;
  channel: string | null;
  mode: string;
};

export default function ContactsPage() {
  const { token } = useAuth();
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [modes, setModes] = useState<MessageMode[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    
    async function fetchData() {
      try {
        const [contactsRes, modesRes] = await Promise.all([
          fetch(`${API_BASE}/contacts`, {
            headers: { Authorization: `Bearer ${token}` }
          }),
          fetch(`${API_BASE}/message-modes?scope=contact`, {
            headers: { Authorization: `Bearer ${token}` }
          })
        ]);
        
        if (contactsRes.ok) setContacts(await contactsRes.json());
        if (modesRes.ok) setModes(await modesRes.json());
      } catch (e) {
        console.error("Failed to fetch data", e);
      } finally {
        setLoading(false);
      }
    }
    
    fetchData();
  }, [token]);

  const handleModeChange = async (contactId: string, newMode: string) => {
    if (!token) return;
    
    const existingMode = modes.find(m => m.contact_id === contactId && m.channel === null);
    
    try {
      if (existingMode) {
        const res = await fetch(`${API_BASE}/message-modes/${existingMode.id}`, {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({ mode: newMode })
        });
        if (res.ok) {
          const updated = await res.json();
          setModes(prev => prev.map(m => m.id === updated.id ? updated : m));
        }
      } else {
        const res = await fetch(`${API_BASE}/message-modes`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`
          },
          body: JSON.stringify({
            scope: "contact",
            contact_id: contactId,
            channel: null,
            mode: newMode
          })
        });
        if (res.ok) {
          const created = await res.json();
          setModes(prev => [...prev, created]);
        }
      }
    } catch (e) {
      console.error("Failed to update message mode", e);
    }
  };

  const getContactMode = (contactId: string) => {
    const m = modes.find(m => m.contact_id === contactId && m.channel === null);
    return m ? m.mode : "default"; // "default" means it falls back to global
  };

  return (
    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-700 ease-out">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="hud-kicker mb-1">// CONTACT POLICY MATRIX</p>
          <h1 className="hud-title">CONTACTS</h1>
        </div>
        <div className="hud-counter w-fit">
          {contacts.length} CONTACTS
        </div>
      </div>

      {loading ? (
        <div className="h-32 flex items-center justify-center">
          <div className="w-5 h-5 border-2 border-white/20 border-t-white/80 rounded-full animate-spin" />
        </div>
      ) : contacts.length === 0 ? (
        <div className="hud-empty">[ NO CONTACTS FOUND ]</div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {contacts.map((contact) => (
            <div key={contact.id} className="hud-panel hud-cut-md flex flex-col justify-between gap-5 p-5 md:flex-row md:items-center">
              <div>
                <h3 className="font-display text-lg font-semibold text-white">{contact.name}</h3>
                <span className="mt-2 inline-block border border-white/10 bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)]/[0.04] px-2 py-0.5 text-xs uppercase tracking-wider text-white/50">
                  {contact.relationship_type}
                </span>
              </div>
              
              <div className="flex flex-col items-start md:items-end gap-2">
                <span className="text-xs text-white/40 uppercase tracking-widest font-mono">Message Mode Override</span>
                <select
                  value={getContactMode(contact.id)}
                  onChange={(e) => handleModeChange(contact.id, e.target.value)}
                  className="hud-select min-w-56"
                >
                  <option value="default">System Default (Fallback)</option>
                  <option value="draft_only">Draft Only</option>
                  <option value="approval_required">Approval Required</option>
                  <option value="trusted">Trusted</option>
                  <option value="autonomous">Autonomous</option>
                </select>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
