import { AgentStreamClient } from './agent-client';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// We mock the native WebSocket
const mockWsInstances: MockWebSocket[] = [];

class MockWebSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSING = 2;
  static CLOSED = 3;

  send = vi.fn();
  close = vi.fn();
  readyState = 0;
  onopen: any = null;
  onclose: any = null;
  onmessage: any = null;
  onerror: any = null;

  constructor(public url: string) {
    mockWsInstances.push(this);
  }
}

(global as any).WebSocket = MockWebSocket;

describe('AgentStreamClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockWsInstances.length = 0;
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('initializes and connects', () => {
    const client = new AgentStreamClient('token-123');
    client.connect();
    expect(mockWsInstances.length).toBe(1);
  });

  it('handles automatic reconnection with exponential backoff', () => {
    const client = new AgentStreamClient('token-123');
    client.connect();
    
    // Simulate connection drop
    const wsInstance = mockWsInstances[0];
    wsInstance.onclose(); // triggers reconnect

    expect(client['connectionState']).toBe('RECONNECTING');
    
    // Fast forward first delay (1000ms)
    vi.advanceTimersByTime(1500);
    expect(mockWsInstances.length).toBe(2);

    // Drop again
    const wsInstance2 = mockWsInstances[1];
    wsInstance2.onclose();
    
    // Fast forward second delay (2000ms)
    vi.advanceTimersByTime(2500);
    expect(mockWsInstances.length).toBe(3);
  });

  it('sends subscribe payload properly', () => {
    const client = new AgentStreamClient('token-123');
    client.connect();
    
    const wsInstance = mockWsInstances[0];
    wsInstance.readyState = 1; // OPEN
    
    client.subscribe('run-123', 5);
    
    expect(wsInstance.send).toHaveBeenCalledWith(JSON.stringify({
      type: 'subscribe',
      agent_run_id: 'run-123',
      last_sequence: 5
    }));
  });
});
