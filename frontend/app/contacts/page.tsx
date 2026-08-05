"use client";

import { useEffect, useState } from "react";
import { useAuth } from "../components/AuthContext";

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
          fetch("http://localhost:8000/api/v1/contacts", {
            headers: { Authorization: `Bearer ${token}` }
          }),
          fetch("http://localhost:8000/api/v1/message-modes?scope=contact", {
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
        const res = await fetch(`http://localhost:8000/api/v1/message-modes/${existingMode.id}`, {
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
        const res = await fetch(`http://localhost:8000/api/v1/message-modes`, {
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
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 ease-out">
      <div>
        <h1 className="text-3xl font-display font-semibold text-white tracking-tight">Contacts</h1>
        <p className="text-white/50 mt-2 text-sm max-w-xl leading-relaxed">
          Manage individuals you communicate with and set contact-specific override behaviors.
        </p>
      </div>

      {loading ? (
        <div className="h-32 flex items-center justify-center">
          <div className="w-5 h-5 border-2 border-white/20 border-t-white/80 rounded-full animate-spin" />
        </div>
      ) : contacts.length === 0 ? (
        <div className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-2xl p-12 text-center">
          <p className="text-white/50 text-sm">No contacts found.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {contacts.map((contact) => (
            <div key={contact.id} className="bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.05)] rounded-2xl p-6 flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div>
                <h3 className="text-lg font-semibold text-white">{contact.name}</h3>
                <span className="inline-block mt-1 px-2 py-0.5 rounded bg-white/5 text-xs text-white/50 border border-white/10 uppercase tracking-wider">
                  {contact.relationship_type}
                </span>
              </div>
              
              <div className="flex flex-col items-start md:items-end gap-2">
                <span className="text-xs text-white/40 uppercase tracking-widest font-mono">Message Mode Override</span>
                <select
                  value={getContactMode(contact.id)}
                  onChange={(e) => handleModeChange(contact.id, e.target.value)}
                  className="bg-black/50 border border-white/10 text-sm text-white rounded-lg px-3 py-2 outline-none focus:border-[#4A90E2]"
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
