'use client';
import React from 'react';
import { AgentEventPayload } from '@/lib/agent-client';

export function ActivityTimeline({ events }: { events: AgentEventPayload[] }) {
  if (!events || events.length === 0) return null;
  
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 max-h-96 overflow-y-auto">
      <h3 className="text-lg font-bold text-gray-800 mb-4">Agent Activity</h3>
      <div className="space-y-4">
        {events.map((evt, idx) => (
          <div key={idx} className="flex space-x-3 items-start">
            <div className="mt-1 w-2 h-2 rounded-full bg-blue-500 shrink-0" />
            <div>
              <p className="text-sm font-medium text-gray-800">{evt.message}</p>
              <span className="text-xs text-gray-400">{new Date(evt.timestamp).toLocaleTimeString()} - {evt.status}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
