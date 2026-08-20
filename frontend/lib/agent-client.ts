export type ConnectionState = 'CONNECTING' | 'CONNECTED' | 'RECONNECTING' | 'DISCONNECTED' | 'FAILED';

export interface AgentEventPayload {
  event_id: string;
  agent_run_id: string;
  plan_id: string | null;
  step_id: string | null;
  type: string;
  status: string;
  message: string;
  timestamp: string;
  metadata: any;
  sequence: number;
}

export type EventCallback = (event: AgentEventPayload) => void;
export type StateCallback = (state: ConnectionState) => void;

export class AgentStreamClient {
  private ws: WebSocket | null = null;
  private url: string;
  private token: string;
  
  private connectionState: ConnectionState = 'DISCONNECTED';
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectBaseDelay = 1000;
  private reconnectTimeoutId: any = null;
  
  private lastSequence = 0;
  private currentRunId: string | null = null;

  private onEventCallback: EventCallback | null = null;
  private onStateCallback: StateCallback | null = null;

  constructor(token: string) {
    this.token = token;
    // Derive WS URL from current window location if in browser
    const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = typeof window !== 'undefined' ? window.location.host : 'localhost:8000';
    this.url = `${protocol}//${host}/api/v1/chat/stream?token=${this.token}`;
  }

  public onEvent(callback: EventCallback) {
    this.onEventCallback = callback;
  }

  public onStateChange(callback: StateCallback) {
    this.onStateCallback = callback;
  }

  private setState(state: ConnectionState) {
    this.connectionState = state;
    if (this.onStateCallback) {
      this.onStateCallback(state);
    }
  }

  public connect() {
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) {
      return;
    }
    this.setState('CONNECTING');
    this.initWebSocket();
  }

  private initWebSocket() {
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.setState('CONNECTED');
        
        // If we were reconnecting an active run, resubscribe
        if (this.currentRunId) {
          this.subscribe(this.currentRunId, this.lastSequence);
        }
      };

      this.ws.onmessage = (messageEvent) => {
        try {
          const data = JSON.parse(messageEvent.data);
          if (data.type === 'ping') {
            this.ws?.send(JSON.stringify({ type: 'pong' }));
            return;
          }
          
          if (data.sequence) {
            this.lastSequence = Math.max(this.lastSequence, data.sequence);
          }
          
          if (this.onEventCallback) {
            this.onEventCallback(data);
          }
        } catch (e) {
          console.error("AgentStreamClient: Error parsing message", e);
        }
      };

      this.ws.onclose = () => {
        this.ws = null;
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.setState('RECONNECTING');
          this.handleReconnect();
        } else {
          this.setState('FAILED');
        }
      };

      this.ws.onerror = (error) => {
        console.error("AgentStreamClient: WebSocket error", error);
      };
      
    } catch (error) {
      console.error("AgentStreamClient: Failed to initialize WebSocket", error);
      this.setState('FAILED');
    }
  }

  private handleReconnect() {
    if (this.reconnectTimeoutId) clearTimeout(this.reconnectTimeoutId);
    
    const delay = this.reconnectBaseDelay * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts++;
    
    this.reconnectTimeoutId = setTimeout(() => {
      this.initWebSocket();
    }, delay);
  }

  public subscribe(runId: string, lastSequence: number = 0) {
    this.currentRunId = runId;
    this.lastSequence = lastSequence;
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        type: 'subscribe',
        agent_run_id: runId,
        last_sequence: lastSequence
      }));
    }
  }

  public sendMessage(text: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({
        message: text
      }));
    } else {
      console.error("Cannot send message: WebSocket is not open");
    }
  }

  public disconnect() {
    if (this.reconnectTimeoutId) clearTimeout(this.reconnectTimeoutId);
    this.reconnectAttempts = this.maxReconnectAttempts; // Prevent auto-reconnect
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setState('DISCONNECTED');
  }
}
