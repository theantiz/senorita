'use client';

import { LogOut } from 'lucide-react';
import { useAuth } from './AuthContext';

export function SidebarLogout() {
  const { logout } = useAuth();

  return (
    <div className="px-4 mt-auto mb-6">
      <button
        onClick={logout}
        className="group flex w-full items-center justify-between border border-white/[0.05] bg-white/[0.02] p-3 transition-all duration-200 hover:bg-white/[0.04]"
      >
        <div className="flex items-center gap-3">
          <LogOut className="h-4 w-4 text-white/40 transition-colors group-hover:text-red-400" strokeWidth={1.7} />
          <span className="font-sans text-xs tracking-wide text-white/50 group-hover:text-white transition-colors">Sign Out</span>
        </div>
      </button>
    </div>
  );
}
