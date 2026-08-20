import { useState, useEffect, useCallback, useRef } from 'react';
import { AgentStreamClient, ConnectionState, AgentEventPayload } from '../lib/agent-client';

export interface PlanStep {
  step_id: string;
  tool_name: string;
  status: string;
  depends_on: string[];
}

export interface AgentState {
  runId: string | null;
  status: string | null;
  planId: string | null;
  goal: string | null;
  steps: PlanStep[];
  events: AgentEventPayload[];
  connectionState: ConnectionState;
  needsConfirmation: boolean;
  confirmationData: any | null;
  error: string | null;
}

const initialState: AgentState = {
  runId: null,
  status: null,
  planId: null,
  goal: null,
  steps: [],
  events: [],
  connectionState: 'DISCONNECTED',
  needsConfirmation: false,
  confirmationData: null,
  error: null,
};

export function useAgentStream(token: string) {
  const [state, setState] = useState<AgentState>(initialState);
  const clientRef = useRef<AgentStreamClient | null>(null);

  useEffect(() => {
    if (!token) return;
    
    const client = new AgentStreamClient(token);
    clientRef.current = client;

    client.onStateChange((connState) => {
      setState(prev => ({ ...prev, connectionState: connState }));
    });

    client.onEvent((event) => {
      setState(prev => {
        // Reducer logic
        const newState = { ...prev };
        
        // Ensure event idempotency by checking sequence or event_id
        if (prev.events.some(e => e.event_id === event.event_id)) {
          return prev;
        }

        if (event.type === 'progress') {
           // Handle legacy string progress
           return { ...newState, events: [...prev.events, event] };
        }

        if (event.type === 'final') {
           newState.status = 'COMPLETED';
           return { ...newState, events: [...prev.events, event] };
        }

        if (event.type === 'error') {
           newState.error = event.message;
           return { ...newState, events: [...prev.events, event] };
        }

        newState.events = [...prev.events, event];

        if (event.agent_run_id && !newState.runId) {
          newState.runId = event.agent_run_id;
        }
        if (event.plan_id && !newState.planId) {
          newState.planId = event.plan_id;
        }

        switch (event.type) {
          case 'agent.started':
            newState.status = 'RUNNING';
            break;
          case 'agent.step_started':
            if (event.step_id) {
               const stepIndex = newState.steps.findIndex(s => s.step_id === event.step_id);
               if (stepIndex >= 0) newState.steps[stepIndex].status = 'RUNNING';
            }
            break;
          case 'agent.step_completed':
            if (event.step_id) {
               const stepIndex = newState.steps.findIndex(s => s.step_id === event.step_id);
               if (stepIndex >= 0) newState.steps[stepIndex].status = 'SUCCESS';
            }
            break;
          case 'agent.step_failed':
            if (event.step_id) {
               const stepIndex = newState.steps.findIndex(s => s.step_id === event.step_id);
               if (stepIndex >= 0) newState.steps[stepIndex].status = 'FAILED';
            }
            break;
          case 'agent.waiting_confirmation':
            newState.status = 'WAITING_FOR_CONFIRMATION';
            newState.needsConfirmation = true;
            newState.confirmationData = event.metadata;
            if (event.step_id) {
               const stepIndex = newState.steps.findIndex(s => s.step_id === event.step_id);
               if (stepIndex >= 0) newState.steps[stepIndex].status = 'PENDING';
            }
            break;
          case 'agent.completed':
            newState.status = 'COMPLETED';
            newState.needsConfirmation = false;
            break;
          case 'agent.failed':
            newState.status = 'FAILED';
            newState.needsConfirmation = false;
            newState.error = event.message;
            break;
          case 'agent.cancelled':
            newState.status = 'CANCELLED';
            newState.needsConfirmation = false;
            break;
        }

        return newState;
      });
    });

    client.connect();

    return () => {
      client.disconnect();
    };
  }, [token]);

  const sendMessage = useCallback((text: string) => {
    // Reset state for new run if we are just starting
    setState(initialState);
    if (clientRef.current) {
      clientRef.current.sendMessage(text);
    }
  }, []);

  const resume = useCallback(async () => {
    if (!state.runId) return;
    try {
      const res = await fetch(`/api/v1/plans/runs/${state.runId}/resume`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        setState(prev => ({ ...prev, needsConfirmation: false, confirmationData: null, status: 'RUNNING' }));
      }
    } catch (e) {
      console.error("Resume failed", e);
    }
  }, [state.runId, token]);

  const cancel = useCallback(async () => {
    if (!state.runId) return;
    try {
      const res = await fetch(`/api/v1/plans/runs/${state.runId}/cancel`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        setState(prev => ({ ...prev, needsConfirmation: false, confirmationData: null, status: 'CANCELLED' }));
      }
    } catch (e) {
      console.error("Cancel failed", e);
    }
  }, [state.runId, token]);

  const recoverState = useCallback(async (runId: string) => {
    if (!token) return;
    try {
      const res = await fetch(`/api/v1/plans/runs/${runId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setState(prev => ({
          ...prev,
          runId: data.agent_run_id,
          status: data.status,
          planId: data.plan_id,
          goal: data.plan?.goal || null,
          steps: data.plan?.steps || [],
          needsConfirmation: data.status === 'WAITING_FOR_CONFIRMATION'
        }));
        if (clientRef.current) {
          // Subscribe with sequence 0 to fetch all missed events, or handle sequence efficiently
          clientRef.current.subscribe(runId, 0); 
        }
      }
    } catch (e) {
      console.error("Recover failed", e);
    }
  }, [token]);

  return {
    state,
    sendMessage,
    resume,
    cancel,
    recoverState
  };
}
