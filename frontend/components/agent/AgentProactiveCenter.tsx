'use client';

import React, { useState } from 'react';
import { Bell, X, Check, Clock } from 'lucide-react';

export interface ProactiveNotification {
  id: string;
  trigger_type: string;
  message: string;
  importance_score: number;
}

export function AgentProactiveCenter({ notifications, onDismiss }: { notifications: ProactiveNotification[], onDismiss: (id: string) => void }) {
  const [isOpen, setIsOpen] = useState(false);

  if (notifications.length === 0) return null;

  return (
    <div className="fixed top-6 right-6 z-50 flex flex-col items-end">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-3 bg-white rounded-full shadow-lg hover:bg-gray-50 border border-gray-100"
      >
        <Bell className="w-5 h-5 text-blue-600" />
        <span className="absolute top-0 right-0 w-3 h-3 bg-red-500 rounded-full border-2 border-white animate-pulse" />
      </button>

      {isOpen && (
        <div className="mt-4 w-80 bg-white rounded-xl shadow-xl border border-gray-200 overflow-hidden">
          <div className="px-4 py-3 bg-gray-50 border-b border-gray-200 flex justify-between items-center">
            <h3 className="text-sm font-semibold text-gray-700">Proactive Alerts</h3>
            <span className="text-xs font-medium bg-blue-100 text-blue-800 px-2 py-1 rounded-full">
              {notifications.length} new
            </span>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {notifications.map((n) => (
              <div key={n.id} className="p-4 border-b border-gray-100 hover:bg-gray-50 transition-colors">
                <div className="flex justify-between items-start mb-2">
                  <span className="text-xs font-bold text-gray-500 uppercase tracking-wider">{n.trigger_type}</span>
                  <div className="flex space-x-1">
                    <button onClick={() => onDismiss(n.id)} className="p-1 text-gray-400 hover:text-gray-600">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <p className="text-sm text-gray-800 leading-snug mb-3">{n.message}</p>
                <div className="flex space-x-2">
                  <button onClick={() => onDismiss(n.id)} className="flex-1 flex items-center justify-center space-x-1 px-2 py-1.5 bg-gray-100 text-gray-700 rounded-lg text-xs font-medium hover:bg-gray-200 transition-colors">
                    <Clock className="w-3 h-3" />
                    <span>Snooze</span>
                  </button>
                  <button onClick={() => onDismiss(n.id)} className="flex-1 flex items-center justify-center space-x-1 px-2 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700 transition-colors">
                    <Check className="w-3 h-3" />
                    <span>Acknowledge</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
