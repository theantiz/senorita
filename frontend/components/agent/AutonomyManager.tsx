'use client';

import React, { useState, useEffect } from 'react';
import { Shield, Lock, ShieldAlert, CheckCircle } from 'lucide-react';
import { api } from '@/lib/api';

const POLICIES = [
  { value: 'SUGGEST', label: 'Suggest Only (Never Auto)', color: 'text-red-600 bg-red-100', icon: Lock },
  { value: 'CONFIRM', label: 'Ask Each Time (Confirm)', color: 'text-orange-600 bg-orange-100', icon: ShieldAlert },
  { value: 'TRUSTED', label: 'Trusted (Ask Once)', color: 'text-blue-600 bg-blue-100', icon: Shield },
  { value: 'FULL_AUTO', label: 'Full Auto (Always Allow)', color: 'text-green-600 bg-green-100', icon: CheckCircle },
];

export function AutonomyManager() {
  const [policies, setPolicies] = useState<any[]>([]);

  useEffect(() => {
    api.get('/autonomy').then(res => setPolicies(res.data)).catch(console.error);
  }, []);

  const updatePolicy = async (scope: string, level: string) => {
    try {
      await api.post('/autonomy', { action_scope: scope, autonomy_level: level });
      const newPolicies = policies.map(p => p.action_scope === scope ? { ...p, autonomy_level: level } : p);
      if (!newPolicies.find(p => p.action_scope === scope)) {
        newPolicies.push({ action_scope: scope, autonomy_level: level });
      }
      setPolicies(newPolicies);
    } catch (err) {
      console.error(err);
    }
  };

  const getLevel = (scope: string) => {
    const p = policies.find(x => x.action_scope === scope);
    return p ? p.autonomy_level : 'CONFIRM';
  };

  const scopes = [
    { id: 'gmail.*', name: 'Read Emails', default: 'FULL_AUTO' },
    { id: 'gmail.send_email', name: 'Send Emails', default: 'CONFIRM' },
    { id: 'calendar.*', name: 'Read Calendar', default: 'FULL_AUTO' },
    { id: 'calendar.create_event', name: 'Create Meetings', default: 'CONFIRM' },
    { id: 'system.*', name: 'System Commands', default: 'CONFIRM' },
  ];

  return (
    <div className="bg-surface border border-border text-foreground shadow-[0_0_15px_var(--glow)] rounded-xl shadow-sm border border-border overflow-hidden mt-6">
      <div className="px-6 py-4 border-b border-border bg-surface-glass flex items-center space-x-3">
        <Shield className="w-5 h-5 text-secondary" />
        <div>
          <h2 className="text-lg font-semibold text-foreground">Action Autonomy Policy</h2>
          <p className="text-sm text-accent">Granular permissions for proactive and autonomous actions</p>
        </div>
      </div>
      <div className="divide-y divide-gray-100">
        {scopes.map(s => {
          const level = getLevel(s.id);
          const policyDef = POLICIES.find(p => p.value === level) || POLICIES[1];
          const Icon = policyDef.icon;
          
          return (
            <div key={s.id} className="p-4 flex items-center justify-between">
              <div>
                <p className="font-medium text-foreground">{s.name}</p>
                <p className="text-xs text-accent">{s.id}</p>
              </div>
              <div className="flex space-x-2">
                <div className={`flex items-center px-3 py-1 rounded-full text-xs font-semibold ${policyDef.color}`}>
                  <Icon className="w-3 h-3 mr-1.5" />
                  {policyDef.label}
                </div>
                <select 
                  className="text-sm border border-border rounded-lg focus:ring-blue-500"
                  value={level}
                  onChange={e => updatePolicy(s.id, e.target.value)}
                >
                  <option value="FULL_AUTO">Full Auto</option>
                  <option value="TRUSTED">Trusted</option>
                  <option value="CONFIRM">Confirm Each Time</option>
                  <option value="SUGGEST">Never Allow</option>
                </select>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
