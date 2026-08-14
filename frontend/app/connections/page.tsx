'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../components/AuthContext';
import { API_BASE } from '@/lib/api';

import { 
  SiGmail,
  SiGooglecalendar,
  SiWhatsapp,
  SiGoogledrive,
  SiApple 
} from 'react-icons/si';
import { FaSlack, FaLinkedin } from 'react-icons/fa';
import { PiMicrosoftOutlookLogo } from 'react-icons/pi';

// ── Types ─────────────────────────────────────────────────────────────────────

interface Integration {
  id: string | null;
  user_id: string | null;
  provider: string;
  status: 'connected' | 'disconnected' | 'error' | 'token_expired';
  scopes: string[];
  permissions: Record<string, boolean>;
  token_expires_at: string | null;
  last_synced_at: string | null;
  created_at: string | null;
}

// ── Provider metadata ─────────────────────────────────────────────────────────

const PROVIDERS: {
  key: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  capabilities: { key: string; label: string; description: string }[];
}[] = [
  {
    key: 'gmail',
    label: 'Gmail',
    description: 'Read, draft and send emails via your Google inbox.',
    icon: <SiGmail className="w-5 h-5" />,
    color: '#EA4335',
    capabilities: [
      { key: 'read', label: 'Read emails', description: 'Let Señorita surface relevant threads' },
      { key: 'draft', label: 'Draft replies', description: 'Auto-compose contextual responses' },
      { key: 'send_automatically', label: 'Send automatically', description: 'Send without manual review (use with care)' },
    ],
  },
  {
    key: 'google_calendar',
    label: 'Google Calendar',
    description: 'One-way sync from Google Calendar for schedule awareness and conflict checks.',
    icon: <SiGooglecalendar className="w-5 h-5" />,
    color: '#4285F4',
    capabilities: [
      { key: 'read', label: 'Read events', description: 'Sync your calendar into Señorita' },
    ],
  },
  {
    key: 'slack',
    label: 'Slack',
    description: 'Monitor channels, summarise threads, and reply on your behalf.',
    icon: <FaSlack className="w-5 h-5" />,
    color: '#4A154B',
    capabilities: [
      { key: 'read', label: 'Read messages', description: 'Surface important threads and mentions' },
      { key: 'send_automatically', label: 'Post automatically', description: 'Reply without manual confirmation' },
    ],
  },
  {
    key: 'whatsapp',
    label: 'WhatsApp',
    description: 'Not available — no compliant personal-account API currently exists.',
    icon: <SiWhatsapp className="w-5 h-5 opacity-50" />,
    color: '#888888',
    capabilities: [],
  },
  {
    key: 'google_drive',
    label: 'Google Drive',
    description: 'Access and summarise documents, spreadsheets and slides.',
    icon: <SiGoogledrive className="w-5 h-5" />,
    color: '#0F9D58',
    capabilities: [
      { key: 'read', label: 'Read files', description: 'Open and summarise your documents' },
    ],
  },
  {
    key: 'outlook',
    label: 'Outlook',
    description: 'Connect your Microsoft email and calendar account.',
    icon: <PiMicrosoftOutlookLogo className="w-5 h-5" />,
    color: '#0078D4',
    capabilities: [
      { key: 'read', label: 'Read emails', description: 'Surface important inbox items' },
      { key: 'draft', label: 'Draft replies', description: 'Auto-compose contextual responses' },
    ],
  },
  {
    key: 'apple_calendar',
    label: 'Apple Calendar',
    description: 'Read iCloud calendar events and sync schedules.',
    icon: <SiApple className="w-5 h-5" />,
    color: '#888888',
    capabilities: [
      { key: 'read', label: 'Read events', description: 'Import your Apple Calendar events' },
    ],
  },
  {
    key: 'linkedin',
    label: 'LinkedIn',
    description: 'Track networking activity and draft connection messages.',
    icon: <FaLinkedin className="w-5 h-5" />,
    color: '#0A66C2',
    capabilities: [
      { key: 'read', label: 'Read profile', description: 'Surface relevant professional context' },
      { key: 'send_automatically', label: 'Send messages', description: 'Draft and send LinkedIn messages' },
    ],
  },
];

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: Integration['status'] }) {
  const config = {
    connected:     { label: 'CONNECTED',     color: '#4ade80', bg: 'rgba(74,222,128,0.08)' },
    disconnected:  { label: 'DISCONNECTED',  color: 'rgba(255,255,255,0.25)', bg: 'rgba(255,255,255,0.04)' },
    error:         { label: 'ERROR',         color: '#f87171', bg: 'rgba(248,113,113,0.08)' },
    token_expired: { label: 'EXPIRED',       color: '#fb923c', bg: 'rgba(251,146,60,0.08)' },
  }[status];

  return (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-0.5 font-mono text-[10px] tracking-widest"
      style={{ color: config.color, backgroundColor: config.bg, border: `1px solid ${config.color}30` }}
    >
      <span
        className="w-1 h-1 rounded-full"
        style={{ backgroundColor: config.color, boxShadow: status === 'connected' ? `0 0 4px ${config.color}` : 'none' }}
      />
      {config.label}
    </span>
  );
}

// ── Toggle switch ─────────────────────────────────────────────────────────────

function Toggle({
  enabled,
  onChange,
  disabled = false,
}: {
  enabled: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      id={`toggle-${Math.random()}`}
      type="button"
      onClick={() => !disabled && onChange(!enabled)}
      disabled={disabled}
      className="relative w-10 h-5 rounded-full transition-all duration-200 focus:outline-none"
      style={{
        backgroundColor: enabled ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.1)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.4 : 1,
      }}
      aria-pressed={enabled}
    >
      <span
        className="absolute top-0.5 w-4 h-4 rounded-full transition-transform duration-200"
        style={{
          left: '2px',
          backgroundColor: enabled ? '#070b14' : 'rgba(255,255,255,0.3)',
          transform: enabled ? 'translateX(20px)' : 'translateX(0)',
        }}
      />
    </button>
  );
}

// ── Integration card ──────────────────────────────────────────────────────────

function ProviderCard({
  meta,
  integration,
  onConnect,
  onDisconnect,
  onTogglePermission,
}: {
  meta: typeof PROVIDERS[0];
  integration: Integration;
  onConnect: (provider: string) => void;
  onDisconnect: (provider: string) => void;
  onTogglePermission: (provider: string, key: string, value: boolean) => void;
}) {
  const connected = integration.status === 'connected';
  const expired   = integration.status === 'token_expired';

  return (
    <article
      className="relative overflow-hidden transition-all duration-300"
      style={{
        background: 'rgba(255,255,255,0.02)',
        border: connected
          ? `1px solid ${meta.color}30`
          : '1px solid rgba(255,255,255,0.06)',
        boxShadow: connected ? `0 0 24px ${meta.color}10` : 'none',
      }}
    >
      {/* Accent line */}
      {connected && (
        <div
          className="absolute top-0 left-0 right-0 h-[1px]"
          style={{ background: `linear-gradient(90deg, transparent, ${meta.color}60, transparent)` }}
        />
      )}

      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 flex items-center justify-center text-xl rounded"
              style={{ background: `${meta.color}15`, border: `1px solid ${meta.color}25` }}
            >
              {meta.icon}
            </div>
            <div>
              <p className="text-sm font-medium text-white tracking-wide">{meta.label}</p>
              <StatusBadge status={integration.status} />
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex gap-2 shrink-0">
            {!connected && !expired && (
              <button
                id={`connect-${meta.key}`}
                onClick={() => onConnect(meta.key)}
                className="px-3 py-1.5 font-mono text-[11px] tracking-widest text-white/80 hover:text-white border border-white/10 hover:border-white/30 transition-all duration-200 hover:bg-white/5"
              >
                CONNECT
              </button>
            )}
            {expired && (
              <button
                id={`reconnect-${meta.key}`}
                onClick={() => onConnect(meta.key)}
                className="px-3 py-1.5 font-mono text-[11px] tracking-widest transition-all duration-200"
                style={{
                  color: '#fb923c',
                  border: '1px solid rgba(251,146,60,0.3)',
                  background: 'rgba(251,146,60,0.05)',
                }}
              >
                RECONNECT
              </button>
            )}
            {connected && (
              <button
                id={`disconnect-${meta.key}`}
                onClick={() => onDisconnect(meta.key)}
                className="px-3 py-1.5 font-mono text-[11px] tracking-widest text-white/30 hover:text-red-400 border border-white/05 hover:border-red-400/20 transition-all duration-200"
              >
                REVOKE
              </button>
            )}
          </div>
        </div>

        {/* Description */}
        <p className="text-xs text-white/40 mb-4 leading-relaxed">{meta.description}</p>

        {/* Capability toggles — only shown when connected */}
        {connected && (
          <div className="space-y-3 pt-3 border-t border-white/[0.05]">
            <p className="font-mono text-[10px] text-white/30 tracking-widest uppercase">Permissions</p>
            {meta.capabilities.map((cap) => (
              <div key={cap.key} className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs text-white/70">{cap.label}</p>
                  <p className="text-[11px] text-white/30 mt-0.5">{cap.description}</p>
                </div>
                <Toggle
                  enabled={!!integration.permissions[cap.key]}
                  onChange={(v) => onTogglePermission(meta.key, cap.key, v)}
                />
              </div>
            ))}

            {integration.last_synced_at && (
              <p className="font-mono text-[10px] text-white/20 pt-1">
                LAST SYNC · {new Date(integration.last_synced_at).toLocaleString()}
              </p>
            )}
          </div>
        )}
      </div>
    </article>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ConnectionsPage() {
  const { token, userId } = useAuth();
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState<string | null>(null);
  const [toastMsg, setToastMsg]         = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const headers = useCallback(
    () => ({ Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }),
    [token],
  );

  const fetchIntegrations = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/integrations`, { headers: headers() });
      if (!res.ok) throw new Error(await res.text());
      setIntegrations(await res.json());
      setError(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [token, headers]);

  useEffect(() => { fetchIntegrations(); }, [fetchIntegrations]);

  const handleConnect = async (provider: string) => {
    if (provider === 'whatsapp') {
      showToast('WhatsApp is not available — no compliant personal-account API currently exists.');
      return;
    }
    try {
      const res = await fetch(
        `${API_BASE}/integrations/${provider}/connect?state=${provider}:${userId ?? 'unknown'}:${Date.now()}`,
        { headers: headers() },
      );
      if (!res.ok) throw new Error(await res.text());
      const { url } = await res.json();
      window.open(url, '_blank', 'noopener,noreferrer');
      showToast(`OAuth window opened for ${provider}. Approve access, then refresh.`);
    } catch (e: any) {
      showToast(`Failed to connect ${provider}: ${e.message}`);
    }
  };


  const handleDisconnect = async (provider: string) => {
    try {
      const res = await fetch(`${API_BASE}/integrations/${provider}`, {
        method: 'DELETE',
        headers: headers(),
      });
      if (!res.ok) throw new Error(await res.text());
      showToast(`${provider} disconnected.`);
      fetchIntegrations();
    } catch (e: any) {
      showToast(`Failed to disconnect ${provider}: ${e.message}`);
    }
  };

  const handleTogglePermission = async (provider: string, key: string, value: boolean) => {
    const current = integrations.find((i) => i.provider === provider);
    if (!current) return;

    const updated = { ...current.permissions, [key]: value };

    // Optimistic update
    setIntegrations((prev) =>
      prev.map((i) => (i.provider === provider ? { ...i, permissions: updated } : i)),
    );

    try {
      const res = await fetch(`${API_BASE}/integrations/${provider}/permissions`, {
        method: 'PATCH',
        headers: headers(),
        body: JSON.stringify({ permissions: updated }),
      });
      if (!res.ok) throw new Error(await res.text());
    } catch (e: any) {
      // Rollback on failure
      setIntegrations((prev) =>
        prev.map((i) => (i.provider === provider ? { ...i, permissions: current.permissions } : i)),
      );
      showToast(`Permission update failed: ${e.message}`);
    }
  };

  const connectedCount = integrations.filter((i) => i.status === 'connected').length;

  return (
    <div className="pb-16">
      {/* ── Toast ── */}
      {toastMsg && (
        <div
          className="fixed top-6 right-6 z-50 px-4 py-3 font-sans text-sm text-white backdrop-blur max-w-xs"

          style={{
            background: 'rgba(7,11,20,0.95)',
            border: '1px solid rgba(255,255,255,0.12)',
            boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
            animation: 'fadeInUp 0.2s ease',
          }}
        >
          {toastMsg}
        </div>
      )}

      {/* ── Header ── */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <span className="font-mono text-[10px] text-white/30 tracking-widest uppercase">07</span>
          <div className="h-px flex-1 bg-white/[0.05]" />
        </div>
        <h1 className="text-2xl font-semibold text-white tracking-tight mb-2">Connections</h1>
        <p className="text-sm text-white/40 leading-relaxed max-w-xl">
          Connect external services so Señorita can act across your digital life.
          All credentials are encrypted at rest — never stored in plaintext.
        </p>

        {!loading && (
          <div className="flex items-center gap-4 mt-5">
            <div
              className="inline-flex items-center gap-2 px-3 py-1.5"
              style={{ background: 'rgba(74,222,128,0.06)', border: '1px solid rgba(74,222,128,0.2)' }}
            >
              <span className="w-1.5 h-1.5 rounded-full bg-[#4ade80]" style={{ boxShadow: '0 0 6px #4ade80' }} />
              <span className="font-mono text-[11px] text-[#4ade80] tracking-widest">
                {connectedCount} / {PROVIDERS.length} ACTIVE
              </span>
            </div>
            <button
              id="refresh-integrations"
              onClick={fetchIntegrations}
              className="font-mono text-[10px] text-white/30 hover:text-white/60 tracking-widest uppercase transition-colors"
            >
              REFRESH
            </button>
          </div>
        )}
      </div>

      {/* ── Loading ── */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="h-40 animate-pulse"
              style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)' }}
            />
          ))}
        </div>
      )}

      {/* ── Error ── */}
      {error && !loading && (
        <div
          className="p-4 mb-6 font-mono text-sm"
          style={{ background: 'rgba(248,113,113,0.05)', border: '1px solid rgba(248,113,113,0.2)', color: '#f87171' }}
        >
          <p className="text-[10px] tracking-widest mb-1 opacity-60">CONNECTION ERROR</p>
          {error}
        </div>
      )}

      {/* ── Provider grid ── */}
      {!loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {PROVIDERS.map((meta) => {
            const integration = integrations.find((i) => i.provider === meta.key) ?? {
              id: null,
              user_id: null,
              provider: meta.key,
              status: 'disconnected' as const,
              scopes: [],
              permissions: {},
              token_expires_at: null,
              last_synced_at: null,
              created_at: null,
            };
            return (
              <ProviderCard
                key={meta.key}
                meta={meta}
                integration={integration}
                onConnect={handleConnect}
                onDisconnect={handleDisconnect}
                onTogglePermission={handleTogglePermission}
              />
            );
          })}
        </div>
      )}

      {/* ── Security note ── */}
      {!loading && (
        <div
          className="mt-8 p-4"
          style={{ background: 'rgba(255,255,255,0.015)', border: '1px solid rgba(255,255,255,0.05)' }}
        >
          <p className="font-mono text-[10px] text-white/30 tracking-widest uppercase mb-2">Security</p>
          <p className="text-xs text-white/30 leading-relaxed">
            OAuth tokens are encrypted with AES-256 (Fernet) before storage.
            Señorita never logs token values and automatically refreshes credentials
            before they expire. You can revoke access at any time — deletion removes
            all stored tokens immediately.
          </p>
        </div>
      )}


      <style jsx>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
