import React from 'react';
import { PlanStep } from '../../hooks/useAgentStream';

export function AgentPlanProgress({ steps, goal }: { steps: PlanStep[], goal: string | null }) {
  if (!steps || steps.length === 0) return null;

  return (
    <div className="border border-white/20 bg-white/5 p-4 mb-4 text-white font-mono text-xs shadow-lg"
         style={{ clipPath: 'polygon(0 0, calc(100% - 10px) 0, 100% 10px, 100% 100%, 10px 100%, 0 calc(100% - 10px))' }}>
      {goal && (
        <div className="mb-3 text-white font-bold border-b border-white/10 pb-2">
          GOAL: {goal}
        </div>
      )}
      <div className="space-y-2">
        {steps.map(step => {
          let icon = '○';
          let color = 'text-white/40';
          let bg = 'bg-transparent';
          
          if (step.status === 'SUCCESS') {
            icon = '✓';
            color = 'text-emerald-400';
          } else if (step.status === 'FAILED') {
            icon = '✗';
            color = 'text-red-400';
          } else if (step.status === 'RUNNING') {
            icon = '●';
            color = 'text-white animate-pulse';
          } else if (step.status === 'PENDING') {
            icon = '●';
            color = 'text-yellow-400 animate-pulse';
          }

          return (
            <div key={step.step_id} className={`flex items-center gap-3 ${color} ${bg} px-2 py-1`}>
              <span className="w-4 text-center">{icon}</span>
              <span className="tracking-wider">{step.tool_name.replace(/_/g, ' ').toUpperCase()}</span>
              {step.status === 'PENDING' && (
                <span className="text-[9px] px-2 py-0.5 border border-yellow-400/50 text-yellow-400 rounded-full ml-auto">
                  WAITING
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
