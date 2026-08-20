import React, { useState } from 'react';

interface Props {
  metadata: any;
  onResume: () => Promise<void>;
  onCancel: () => Promise<void>;
}

export function AgentConfirmationCard({ metadata, onResume, onCancel }: Props) {
  const [loading, setLoading] = useState(false);

  const handleConfirm = async () => {
    setLoading(true);
    try {
      await onResume();
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    setLoading(true);
    try {
      await onCancel();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="border border-yellow-500/50 bg-yellow-500/10 p-5 mb-4 text-white font-mono text-sm shadow-[0_0_15px_rgba(234,179,8,0.15)]"
         style={{ clipPath: 'polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 10px 100%, 0 calc(100% - 10px))' }}>
      
      <div className="flex items-center gap-2 text-yellow-400 mb-3 font-bold border-b border-yellow-500/20 pb-2">
        <div className="w-2 h-2 bg-yellow-400 rotate-45 animate-pulse" />
        AUTHORIZATION REQUIRED
      </div>

      <div className="text-white/80 text-xs mb-5 whitespace-pre-wrap">
        {metadata?.message || "The agent requires confirmation to proceed with a sensitive action."}
      </div>

      <div className="flex gap-3 mt-4">
        <button
          onClick={handleConfirm}
          disabled={loading}
          className="flex-1 bg-yellow-500 hover:bg-yellow-400 text-black font-bold py-2 px-4 transition-colors disabled:opacity-50"
          style={{ clipPath: 'polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 8px 100%, 0 calc(100% - 8px))' }}
        >
          {loading ? 'PROCESSING...' : 'AUTHORIZE'}
        </button>
        <button
          onClick={handleCancel}
          disabled={loading}
          className="flex-1 border border-white/20 hover:border-red-500 hover:text-red-400 hover:bg-red-500/10 text-white/60 py-2 px-4 transition-colors disabled:opacity-50"
          style={{ clipPath: 'polygon(0 0, calc(100% - 8px) 0, 100% 8px, 100% 100%, 8px 100%, 0 calc(100% - 8px))' }}
        >
          CANCEL
        </button>
      </div>
    </div>
  );
}
