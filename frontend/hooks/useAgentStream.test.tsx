import { renderHook, act } from '@testing-library/react';
import { useAgentStream } from './useAgentStream';
import { vi, describe, it, expect, beforeEach } from 'vitest';

let mockEventCallback: any = null;

vi.mock('../lib/agent-client', () => {
  const MockAgentStreamClient = class {
    onStateChange = vi.fn();
    onEvent = vi.fn().mockImplementation((cb) => {
      mockEventCallback = cb;
    });
    connect = vi.fn();
    disconnect = vi.fn();
    subscribe = vi.fn();
    sendMessage = vi.fn();
  };
  return {
    AgentStreamClient: MockAgentStreamClient
  };
});

describe('useAgentStream Reducer', () => {
  
  beforeEach(() => {
    vi.clearAllMocks();
    mockEventCallback = null;
  });

  it('handles agent.started and sets status', () => {
    const { result } = renderHook(() => useAgentStream('test-token'));
    
    act(() => {
      mockEventCallback({
        type: 'agent.started',
        agent_run_id: 'run-123',
        event_id: 'evt-1',
        sequence: 1,
        status: 'running',
        message: 'started'
      });
    });

    expect(result.current.state.runId).toBe('run-123');
    expect(result.current.state.status).toBe('RUNNING');
    expect(result.current.state.events).toHaveLength(1);
  });

  it('prevents duplicate events from corrupting state', () => {
    const { result } = renderHook(() => useAgentStream('test-token'));
    
    act(() => {
      const event = {
        type: 'agent.started',
        agent_run_id: 'run-123',
        event_id: 'evt-1',
        sequence: 1,
        status: 'running',
        message: 'started'
      };
      mockEventCallback(event);
      mockEventCallback(event); // Duplicate
    });

    expect(result.current.state.events).toHaveLength(1);
  });

  it('handles waiting_confirmation safely', () => {
    const { result } = renderHook(() => useAgentStream('test-token'));
    
    act(() => {
      mockEventCallback({
        type: 'agent.waiting_confirmation',
        agent_run_id: 'run-123',
        event_id: 'evt-2',
        sequence: 2,
        status: 'waiting',
        message: 'confirm?',
        metadata: { message: "Schedule meeting?" }
      });
    });

    expect(result.current.state.status).toBe('WAITING_FOR_CONFIRMATION');
    expect(result.current.state.needsConfirmation).toBe(true);
    expect(result.current.state.confirmationData.message).toBe("Schedule meeting?");
  });
});
