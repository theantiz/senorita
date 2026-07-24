'use client';

import { useAuth } from './AuthContext';

export function SidebarLogout() {
  const { logout } = useAuth();

  return (
    <div className="px-4 mt-auto mb-6">
      <button
        onClick={logout}
        className="group flex items-center justify-between w-full p-3 rounded-lg border border-[rgba(255,255,255,0.05)] bg-[rgba(255,255,255,0.02)] hover:bg-[rgba(255,255,255,0.04)] transition-all duration-200"
      >
        <div className="flex items-center gap-3">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="w-4 h-4 text-white/40 group-hover:text-red-400 transition-colors">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75" />
          </svg>
          <span className="font-sans text-xs tracking-wide text-white/50 group-hover:text-white transition-colors">Sign Out</span>
        </div>
      </button>
    </div>
  );
}
