'use client';
import React, { useState } from 'react';

const INTEGRATIONS = [
  { id: 'gmail', name: 'Gmail', permissions: ['Read', 'Send', 'Delete'] },
  { id: 'calendar', name: 'Google Calendar', permissions: ['Read', 'Create', 'Modify', 'Delete'] },
  { id: 'slack', name: 'Slack', permissions: ['Read', 'Send'] },
  { id: 'pc', name: 'Local PC', permissions: ['Read Files', 'Execute Commands'] },
  { id: 'voice', name: 'Voice Input', permissions: ['Listen'] }
];

export function PermissionCenter() {
  const [active, setActive] = useState<Record<string, Record<string, boolean>>>({});
  
  const toggle = (app: string, perm: string) => {
    setActive(prev => ({
      ...prev,
      [app]: { ...prev[app], [perm]: !(prev[app]?.[perm]) }
    }));
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <h2 className="text-lg font-bold text-gray-800">Permission Center</h2>
        <p className="text-sm text-gray-500">Manage what Señorita is allowed to access autonomously.</p>
      </div>
      <div className="divide-y divide-gray-100 p-6 space-y-6">
        {INTEGRATIONS.map(integ => (
          <div key={integ.id} className="pt-4 first:pt-0">
            <h3 className="font-semibold text-gray-700 mb-2">{integ.name}</h3>
            <div className="flex flex-wrap gap-2">
              {integ.permissions.map(perm => (
                <button
                  key={perm}
                  onClick={() => toggle(integ.id, perm)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${active[integ.id]?.[perm] ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}
                >
                  {perm} {active[integ.id]?.[perm] ? '✓' : ''}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
