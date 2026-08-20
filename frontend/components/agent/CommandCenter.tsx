'use client';
import React from 'react';
import { ActivityTimeline } from './ActivityTimeline';
import { PermissionCenter } from './PermissionCenter';
import { AgentMemoryManager } from './AgentMemoryManager';
import { AgentPreferenceManager } from './AgentPreferenceManager';
import { AgentProactiveCenter } from './AgentProactiveCenter';

export function CommandCenter({ events, notifications, onDismissNotification }: any) {
  return (
    <div className="max-w-7xl mx-auto p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
      <div className="md:col-span-2 space-y-6">
        <ActivityTimeline events={events} />
        <AgentMemoryManager />
        <AgentPreferenceManager />
      </div>
      <div className="space-y-6">
        <AgentProactiveCenter notifications={notifications} onDismiss={onDismissNotification} />
        <PermissionCenter />
      </div>
    </div>
  );
}
