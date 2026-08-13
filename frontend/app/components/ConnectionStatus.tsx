"use client";

import React, { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

export function ConnectionStatus() {
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    let mounted = true;
    
    const checkConnection = async () => {
      try {
        await apiFetch("/healthz");
        if (mounted) setIsOnline(true);
      } catch (err) {
        if (mounted) setIsOnline(false);
      }
    };

    // Check immediately
    checkConnection();

    // Then poll every 10 seconds
    const interval = setInterval(checkConnection, 10000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="mb-2 flex items-center">
      <span 
        className={`inline-block w-2 h-2 rounded-full mr-2 transition-colors duration-500 ${
          isOnline ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]"
        }`} 
      />
      <span className="font-mono text-[10px] text-white/50 tracking-widest uppercase transition-colors duration-500">
        {isOnline ? "SYS_ONLINE" : "SYS_OFFLINE"}
      </span>
    </div>
  );
}
